"""API route definitions for the metadata API."""

import json
import logging
from copy import deepcopy
from typing import Any

from fastapi import APIRouter, Body, HTTPException, Query, Request
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.responses import HTMLResponse, JSONResponse

from metadata_api import models, utils
from metadata_api.adapt_schema import adapt_schema
from metadata_api.memcached import cache
from metadata_api.settings import settings
from metadata_api.tasks import renew_cache_task

logger = logging.getLogger(__name__)

router = APIRouter()


# ------------------------------------------------------------------------------
# Metadata retrieval endpoints
# ------------------------------------------------------------------------------

@router.get("/", response_model=models.AllResouresList, tags=["Metadata retrieval"], summary="List all resources")
def list_resources(
    resource_type: utils.ResourceTypes | None = Query(  # type: ignore
        default=None, alias="resource-type", title="Resource type", example="corpus", enum=settings.RESOURCE_TYPES
    ),
    resource: str | None = Query(default=None, title="Resource ID", example="attasidor"),
    legacy: bool = Query(
        default=True, description="If true, use legacy response format ('corpora' instead of 'corpus' etc.)."
    ),
) -> JSONResponse:
    """List metadata for all resources, all resources of a given type or a single resource by ID.

    Refer to the `/schema` endpoint for the exact JSON schema of the metadata.
    """
    if resource and resource_type:
        raise HTTPException(
            status_code=400,
            detail="Specify either 'resource' or 'resource_type', not both.",
        )
    with cache.get_client() as cache_client:
        if resource_type:
            # Return all resources of the given type
            resource_type = resource_type.value
            resource_file = f"{resource_type}.json"
            filtered = utils.load_json(settings.STATIC / resource_file, cache_client=cache_client)
            data = utils.dict_to_list(filtered)
            return JSONResponse({"resource_type": resource_type, "hits": len(data), "resources": data})
        if resource:
            # Return a single resource by ID
            resources_dict = utils.load_resources(settings.RESOURCES, settings.STATIC, cache_client=cache_client)
            return JSONResponse(utils.get_single_resource(resource, resources_dict, cache_client=cache_client))
        # Return all resources in legacy or modern format
        resources_dict = utils.load_resources(
            settings.RESOURCES, settings.STATIC, cache_client=cache_client, legacy=legacy
        )
        return JSONResponse({k: utils.dict_to_list(v) for k, v in resources_dict.items()})


def _resource_list_factory(resource_type: str) -> Any:
    """Create resource list endpoint functions.

    Args:
        resource_type: The resource type in plural (e.g. 'corpora').
    """
    def resource_list() -> JSONResponse:
        with cache.get_client() as cache_client:
            filtered = utils.load_json(
                settings.STATIC / settings.RESOURCES.get(resource_type, ""),
                cache_client=cache_client,
            )
        data = utils.dict_to_list(filtered)
        return JSONResponse({"resource_type": resource_type, "hits": len(data), "resources": data})

    return resource_list


@router.get("/list-ids", response_model=list[str], tags=["Metadata retrieval"], summary="List resource IDs")
def list_ids() -> JSONResponse:
    """List all resource IDs."""
    with cache.get_client() as cache_client:
        resources = utils.load_resources(settings.RESOURCES, settings.STATIC, cache_client=cache_client)
    return JSONResponse(sorted([k for resource_type in resources.values() for k in resource_type]))


@router.get("/bibtex", response_model=models.BibtexResponse, tags=["Metadata retrieval"], summary="Get BibTeX citation")
def bibtex(
    resource: str = Query(title="Resource ID", example="attasidor"),
) -> JSONResponse:
    """Return bibtex citation as text."""
    with cache.get_client() as cache_client:
        resources_dict = utils.load_resources(settings.RESOURCES, settings.STATIC, cache_client=cache_client)
        return JSONResponse({"bibtex": utils.get_bibtex(resource, resources_dict)})


for resource_type in settings.RESOURCES:
    res_type_name = settings.RESOURCES[resource_type].split(".")[0]
    # Add deprecated route for backward compatibility
    router.add_api_route(
        f"/{resource_type}",
        _resource_list_factory(resource_type),
        response_model=models.ResourceList,
        methods=["GET"],
        deprecated=True,
        tags=["Metadata retrieval"],
        summary=f"List {res_type_name}",
        description=f"List all resources of type '{res_type_name}'."
        f"\n\nPlease use `/?resource_type={res_type_name}` route instead."
        "\n\nRefer to the /schema endpoint for the exact JSON schema of the metadata.",
    )


@router.get(
    "/collections",
    response_model=models.CollectionsList,
    deprecated=True,
    tags=["Metadata retrieval"],
    summary="List collections",
)
def list_collections() -> JSONResponse:
    """List all resource collections.

    Refer to the `/schema` endpoint for the exact JSON schema of the metadata.
    """
    with cache.get_client() as cache_client:
        collections = utils.load_json(settings.STATIC / settings.COLLECTIONS_FILE, cache_client=cache_client)
        data = utils.dict_to_list(collections)
        return JSONResponse({"hits": len(data), "resources": data})


# ------------------------------------------------------------------------------
# MISC endpoints
# ------------------------------------------------------------------------------


@router.get(
    "/check-id-availability",
    response_model=models.IdAvailabilityResponse,
    tags=["MISC"],
    summary="Check resource ID availability",
)
def check_id(
    resource_id: str = Query(alias="id", title="Resource ID", example="my-new-resource"),
) -> JSONResponse:
    """Check if a given resource ID is available."""
    with cache.get_client() as cache_client:
        resources = utils.load_resources(settings.RESOURCES, settings.STATIC, cache_client=cache_client)
        resource_ids = [k for resource_type in resources.values() for k in resource_type]
        return JSONResponse({"id": resource_id, "available": resource_id not in resource_ids})


@router.get("/schema", response_model=dict, tags=["MISC"])
def schema() -> JSONResponse:
    """Return JSON schema for the metadata."""
    schema_file = settings.METADATA_DIR / settings.SCHEMA_FILE
    return JSONResponse(adapt_schema(json.loads(schema_file.read_text(encoding="UTF-8"))))


# ------------------------------------------------------------------------------
# Cache management endpoints
# ------------------------------------------------------------------------------

def _renew_cache(
    request_method: str,
    resource_paths: str | None,
    debug: bool,
    offline: bool,
    payload: dict | None,
) -> JSONResponse:
    """Shared renew-cache logic for GET/POST routes."""
    paths_list = resource_paths.split(",") if resource_paths else None
    try:
        task = renew_cache_task.delay(
            request_method=request_method,
            resource_paths=paths_list,
            debug=debug,
            offline=offline,
            payload=payload if request_method == "POST" else None,
        )
    except Exception as e:
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
        example="corpus/attasidor,lexicon/saldo",
    ),
    debug: bool = Query(default=False, description="If true, log debug info while parsing YAML files."),
    offline: bool = Query(default=False, description="If true, skip getting file info for downloadables."),
) -> JSONResponse:
    """Trigger cache renewal as a background job (GET).

    Resources specified in the "resource-paths" query parameter will be reprocessed. If no resources are specified, all
    resources are reprocessed.
    """
    return _renew_cache("GET", resource_paths, debug, offline, payload=None)


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


@router.get("/doc", tags=["Documentation"], summary="OpenAPI schema", deprecated=True)
async def openapi_alias(request: Request) -> dict:
    """Serve the same JSON as /openapi.json (Backward-compatible alias)."""
    return request.app.openapi()


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
