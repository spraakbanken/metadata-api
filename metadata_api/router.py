"""API route definitions for the metadata API."""

import json
import logging
from copy import deepcopy
from typing import Any, cast

import jsonschema_rs
import redis
import yaml
from celery import Task
from fastapi import APIRouter, Body, HTTPException, Query, Request
from fastapi import Path as FastAPIPath
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.responses import HTMLResponse, JSONResponse

from metadata_api import models, utils
from metadata_api.adapt_schema import adapt_schema
from metadata_api.memcached import cache
from metadata_api.settings import settings
from metadata_api.tasks import renew_cache_task

logger = logging.getLogger(__name__)

router = APIRouter()

# Redis client for managing pending renew-cache tasks
redis_client = redis.Redis.from_url(settings.CELERY_BROKER_URL)


# ------------------------------------------------------------------------------
# Metadata retrieval endpoints
# ------------------------------------------------------------------------------


@router.get(
    "/",
    response_model=models.AllResouresList | models.ResourceList | models.Resource,
    tags=["Metadata retrieval"],
    summary="List resources",
)
def list_resources(
    resource_type: str | None = Query(
        default=None, alias="resource-type", title="Resource type", examples=["corpus"], enum=settings.RESOURCE_TYPES
    ),
    resource: str | None = Query(default=None, title="Resource ID", examples=["attasidor"]),
) -> JSONResponse:
    """List metadata for all resources, all resources of a given type or a single resource by ID.

    Refer to the `/response-schema` endpoint for the exact JSON schema of a `/resource=<resource_id>` response.
    """
    if resource and resource_type:
        raise HTTPException(
            status_code=400,
            detail="Specify either 'resource' or 'resource_type', not both.",
        )
    if resource_type and resource_type not in settings.RESOURCE_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid resource type '{resource_type}'. Must be one of: {', '.join(settings.RESOURCE_TYPES)}.",
        )
    with cache.get_client() as cache_client:
        if resource_type:
            # Return all resources of the given type
            resource_file = f"{resource_type}.json"
            filtered = utils.load_json(settings.STATIC / resource_file, cache_client=cache_client)
            data = utils.dict_to_list(filtered)
            return JSONResponse({"resource_type": resource_type, "hits": len(data), "resources": data})
        if resource:
            # Return a single resource by ID
            resources_dict = utils.load_resources(settings.RESOURCES, settings.STATIC, cache_client=cache_client)
            return JSONResponse(utils.get_single_resource(resource, resources_dict, cache_client=cache_client))
        # Return all resources
        resources_dict = utils.load_resources(settings.RESOURCES, settings.STATIC, cache_client=cache_client)
        return JSONResponse({k: utils.dict_to_list(v) for k, v in resources_dict.items()})


@router.get(
    "/source/{resource_type}/{resource_id}",
    response_model=dict[str, Any],
    tags=["Metadata retrieval"],
    summary="Get source metadata YAML as JSON",
)
def get_source_metadata(
    resource_type: str = FastAPIPath(..., title="Resource type", examples=["corpus"]),
    resource_id: str = FastAPIPath(..., title="Resource ID", examples=["attasidor"]),
) -> JSONResponse:
    """Return the source metadata YAML file from disk as JSON without applying metadata processing."""
    if resource_type not in settings.RESOURCE_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid resource type '{resource_type}'. Must be one of: {', '.join(settings.RESOURCE_TYPES)}.",
        )

    yaml_root = (settings.METADATA_DIR / settings.YAML_DIR).resolve()
    filepath = (yaml_root / resource_type / f"{resource_id}.yaml").resolve()
    # Ensure filepath is inside the YAML directory
    try:
        filepath.relative_to(yaml_root)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid resource path.") from e
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="Resource source file not found.")

    try:
        # YAML safe_load() - handle dates as strings
        yaml.constructor.SafeConstructor.yaml_constructors["tag:yaml.org,2002:timestamp"] = (
            yaml.constructor.SafeConstructor.yaml_constructors["tag:yaml.org,2002:str"]
        )
        with filepath.open(encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError:
        logger.exception("Invalid YAML in source metadata file '%s'", filepath)
        raise HTTPException(status_code=500, detail="Failed to parse source metadata YAML.") from None

    return JSONResponse(data)


@router.get("/list-ids", response_model=list[str], tags=["Metadata retrieval"], summary="List resource IDs")
def list_ids() -> JSONResponse:
    """List all resource IDs."""
    with cache.get_client() as cache_client:
        resources = utils.load_resources(settings.RESOURCES, settings.STATIC, cache_client=cache_client)
    return JSONResponse(sorted([k for resource_type in resources.values() for k in resource_type]))


@router.get("/bibtex", response_model=models.BibtexResponse, tags=["Metadata retrieval"], summary="Get BibTeX citation")
def bibtex(
    resource: str = Query(title="Resource ID", examples=["attasidor"]),
) -> JSONResponse:
    """Return bibtex citation as text."""
    with cache.get_client() as cache_client:
        resources_dict = utils.load_resources(settings.RESOURCES, settings.STATIC, cache_client=cache_client)
        return JSONResponse({"bibtex": utils.get_bibtex(resource, resources_dict)})


# ------------------------------------------------------------------------------
# MISC tools endpoints
# ------------------------------------------------------------------------------


@router.get(
    "/check-id-availability",
    response_model=models.IdAvailabilityResponse,
    tags=["MISC tools"],
    summary="Check resource ID availability",
)
def check_id(
    resource_id: str = Query(alias="id", title="Resource ID", examples=["my-new-resource"]),
) -> JSONResponse:
    """Check if a given resource ID is available."""
    with cache.get_client() as cache_client:
        resources = utils.load_resources(settings.RESOURCES, settings.STATIC, cache_client=cache_client)
        resource_ids = [k for resource_type in resources.values() for k in resource_type]
        return JSONResponse({"id": resource_id, "available": resource_id not in resource_ids})


@router.get("/resource-schema", response_model=dict, tags=["MISC tools"])
def resource_schema() -> JSONResponse:
    """Return the JSON schema which is used to validate the metadata YAML files."""
    schema_file = settings.METADATA_DIR / settings.SCHEMA_FILE
    return JSONResponse(json.loads(schema_file.read_text(encoding="UTF-8")))


@router.post("/validate-resource", response_model=models.ValidateResourceResponse, tags=["MISC tools"])
def validate_resource(resource: dict = Body(..., description="The resource metadata to validate")) -> JSONResponse:
    """Validate the provided resource metadata against the resource JSON schema."""
    schema_validator = utils.get_schema_validator(settings.METADATA_DIR / settings.SCHEMA_FILE)
    if schema_validator is None:
        raise HTTPException(status_code=500, detail="Failed to load schema validator.")
    try:
        schema_validator.validate(resource)
    except jsonschema_rs.ValidationError as e:
        return JSONResponse({"valid": False, "message": e.message})
    except Exception:
        return JSONResponse({"valid": False, "message": "An unexpected error occurred during validation."})

    return JSONResponse({"valid": True, "message": "Resource metadata is valid."})


# ------------------------------------------------------------------------------
# Cache management endpoints
# ------------------------------------------------------------------------------


def _renew_cache(
    request_method: str,
    resource_paths: str | None,
    debug: bool,
    offline: bool,
    payload: dict | None = None,
    purge_license_cache: bool = False,
) -> JSONResponse:
    paths_list = resource_paths.split(",") if resource_paths else None

    # Do atomic increment of pending counter
    logger.info("Pending renew-cache tasks: %s", int(cast(int, redis_client.get(settings.PENDING_KEY))) or 0)
    pending = cast(int, redis_client.incr(settings.PENDING_KEY))
    if pending > settings.MAX_PENDING:
        # Too many pending tasks, roll back the increment
        redis_client.decr(settings.PENDING_KEY)
        raise HTTPException(status_code=409, detail="Too many cache renewals queued. Try again later.")

    try:
        task = cast(Task, renew_cache_task).apply_async(
            kwargs={
                "request_method": request_method,
                "resource_paths": paths_list,
                "debug": debug,
                "offline": offline,
                "payload": payload if request_method == "POST" else None,
                "purge_license_cache": purge_license_cache,
            }
        )
    except Exception as e:
        # Roll back the slot if enqueue failed
        redis_client.decr(settings.PENDING_KEY)
        raise HTTPException(status_code=500, detail=str(e)) from e

    return JSONResponse({"task_id": task.id, "message": "Cache renewal triggered in background."})


@router.get(
    "/renew-cache",
    response_model=models.RenewCacheResponse,
    status_code=202,
    tags=["Cache management"],
)
def renew_cache_get(
    resource_paths: str | None = Query(
        default=None,
        alias="resource-paths",
        description="Comma-separated list of specific resources to reprocess (<resource_type/resource_id>).",
        examples=["corpus/attasidor,lexicon/saldo"],
    ),
    debug: bool = Query(default=False, description="If true, log debug info while parsing YAML files."),
    offline: bool = Query(default=False, description="If true, skip getting file info for downloadables."),
    purge_license_cache: bool = Query(
        default=False,
        alias="purge-license-cache",
        description="If true, re-download the license information before parsing YAML files.",
    ),
) -> JSONResponse:
    """Trigger cache renewal as a background job (GET).

    Resources specified in the "resource-paths" query parameter will be reprocessed. If no resources are specified, all
    resources are reprocessed.
    """
    return _renew_cache("GET", resource_paths, debug, offline, purge_license_cache=purge_license_cache)


@router.post(
    "/renew-cache",
    response_model=models.RenewCacheResponse,
    status_code=202,
    tags=["Cache management"],
)
def renew_cache_post(
    debug: bool = Query(default=False, description="If true, log debug info while parsing YAML files."),
    offline: bool = Query(default=False, description="If true, skip getting file info for downloadables."),
    payload: dict | None = Body(default=None, description="Payload from GitHub webhook."),
) -> JSONResponse:
    """Trigger cache renewal as a background job (POST).

    The resources to be reprocessed are determined based on the changed files in the webhook payload.
    """
    return _renew_cache("POST", None, debug, offline, payload)


# ------------------------------------------------------------------------------
# Documentation endpoints
# ------------------------------------------------------------------------------


@router.get("/openapi.json", tags=["Documentation"], summary="OpenAPI schema", response_class=JSONResponse)
async def openapi_json(request: Request) -> JSONResponse:
    """Serve the OpenAPI specification as JSON data."""
    schema = deepcopy(request.app.openapi())  # Avoid mutating the cached base
    base_url = str(request.base_url).rstrip("/")
    if settings.ENV == "development":
        schema["servers"].insert(0, {"url": f"{base_url}{settings.ROOT_PATH}", "description": "Current server"})
    return JSONResponse(schema)


@router.get("/response-schema", response_model=dict, tags=["Documentation"])
def response_schema() -> JSONResponse:
    """Return JSON schema for the resource listings generated by the `/?resource=<resource_id>` endpoint.

    This schema is adapted from the resource metadata schema to reflect the structure of the API response data.
    """
    schema_file = settings.METADATA_DIR / settings.SCHEMA_FILE
    return JSONResponse(adapt_schema(json.loads(schema_file.read_text(encoding="UTF-8"))))


@router.get("/redoc", tags=["Documentation"], summary="ReDoc API documentation", response_class=HTMLResponse)
def overridden_redoc(request: Request) -> HTMLResponse:
    """Serve ReDoc documentation."""
    root_path = request.scope.get("root_path", "") or ""
    openapi_path = request.app.router.url_path_for("openapi_json")
    return get_redoc_html(
        openapi_url=f"{root_path}{openapi_path}",
        title=f"{request.app.title} - ReDoc",
        redoc_favicon_url=str(request.url_for("static", path="favicon.png")),
    )


@router.get("/docs", tags=["Documentation"], summary="Swagger UI documentation", response_class=HTMLResponse)
def overridden_swagger(request: Request) -> HTMLResponse:
    """Serve Swagger UI documentation."""
    root_path = request.scope.get("root_path", "") or ""
    openapi_path = request.app.router.url_path_for("openapi_json")
    return get_swagger_ui_html(
        openapi_url=f"{root_path}{openapi_path}",
        title=f"{request.app.title} - Swagger UI",
        swagger_favicon_url=str(request.url_for("static", path="favicon.png")),
    )
