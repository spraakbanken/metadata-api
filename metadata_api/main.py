"""Main application file for the Metadata API."""

import logging
import traceback
from collections.abc import AsyncGenerator, Callable
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

import yaml
from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from metadata_api import utils
from metadata_api.memcached import cache
from metadata_api.router import router
from metadata_api.settings import settings

API_VERSION = utils.get_version_from_pyproject(Path("pyproject.toml"))

# Configure logging: always log to console; optionally also to file
log_dir = settings.LOG_DIR
handlers: list[logging.Handler] = [logging.StreamHandler()]
if settings.LOG_TO_FILE:
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"metadata_api_{datetime.now().strftime('%Y-%m-%d')}.log"
    handlers.append(logging.FileHandler(log_file))

logging.basicConfig(level=settings.LOG_LEVEL, format=settings.LOG_FORMAT, handlers=handlers)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator:  # noqa: RUF029
    """Manage application startup and shutdown."""
    logger.info("Starting Metadata API version %s", API_VERSION)
    cache.initialize(settings.MEMCACHED_SERVER)
    yield


app = FastAPI(
    title="Metadata API",
    version=API_VERSION,
    root_path=settings.ROOT_PATH,
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=settings.STATIC), name="static")


@app.middleware("http")
async def log_requests(request: Request, call_next: Callable) -> JSONResponse:
    """Middleware to log incoming requests."""
    if request.method != "OPTIONS":
        logger.info("Request: %s %s", request.method, request.url)
    return await call_next(request)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:  # noqa: ARG001, RUF029
    """Handle request validation errors with detailed human-readable feedback."""
    logger.warning("Validation error: %s", exc)
    exc_errors = jsonable_encoder(exc.errors())

    # Parse pydantic errors into a list of readable strings
    errors = []
    for pydantic_error in exc_errors:
        loc = pydantic_error["loc"]
        # Format loc into a string, e.g. "body: field.subfield" or "query: param"
        field_string = loc[0] + ": " + ".".join(loc[1:]) if loc[0] in {"body", "query", "path"} else str(loc)
        errors.append(field_string + f" ({pydantic_error['msg']})")

    return JSONResponse(
        {"error": "Validation Error", "detail": errors}, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:  # noqa: ARG001, RUF029
    """Handle HTTP errors (e.g., 400/404) with concise messages."""
    if exc.status_code == status.HTTP_400_BAD_REQUEST:
        logger.warning("Bad Request: %s", exc.detail)
        message = "Bad Request"
    elif exc.status_code == status.HTTP_404_NOT_FOUND:
        logger.warning("Not Found: %s", exc.detail)
        message = "Not Found"
    else:
        logger.warning("HTTP %s: %s", exc.status_code, exc.detail)
        message = exc.detail or "HTTP Error"
    return JSONResponse({"Error": message}, status_code=exc.status_code)


@app.exception_handler(Exception)
async def server_error_handler(request: Request, exc: Exception) -> JSONResponse:  # noqa: ARG001, RUF029
    """Handle uncaught server errors (500)."""
    tb = traceback.format_exc()
    logger.error("Server Error: %s\nTraceback: %s", exc, tb)
    body = {"Error": "Internal Server Error"}
    if settings.ENV == "development":
        body["detail"] = str(exc)
        body["traceback"] = tb
    return JSONResponse(body, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


app.include_router(router)


# ------------------------------------------------------------------------------
# Custom OpenAPI schema
# ------------------------------------------------------------------------------
def custom_openapi() -> dict:
    """Customize the OpenAPI schema.

    Returns:
        dict: The OpenAPI schema
    """
    if app.openapi_schema:
        return app.openapi_schema
    # Load OpenAPI info from the YAML file
    openapi_info_path = Path(__file__).parent / "openapi_info.yaml"
    with openapi_info_path.open("r", encoding="utf-8") as file:
        openapi_info = yaml.safe_load(file)
    openapi_schema = get_openapi(
        title=openapi_info["info"]["title"],
        version=API_VERSION,
        routes=app.routes,
    )
    openapi_schema["info"] = openapi_info["info"]
    openapi_schema["info"]["version"] = API_VERSION  # Need to set version again since it is overridden above
    openapi_schema["tags"] = openapi_info["tags"]
    openapi_schema["servers"] = openapi_info["servers"]

    # Cache the modified OpenAPI schema
    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi
