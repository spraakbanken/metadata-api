"""Routes for the metadata API."""

import json
import logging
from pathlib import Path

import yaml
from flask import Blueprint, Response, current_app, jsonify, request

from . import utils
from .adapt_schema import adapt_schema
from .tasks import renew_cache_task

general = Blueprint("general", __name__)
logger = logging.getLogger(__name__)
version = utils.get_version_from_pyproject()


@general.route("/doc")
def documentation() -> tuple[Response, int]:
    """Serve API documentation as json data.

    Returns:
        The API documentation as a json response.
    """
    static_folder = current_app.static_folder
    if static_folder is None:
        return jsonify({"error": "Static folder is not configured."}), 500
    spec_file = Path(static_folder) / "apidoc.yaml"
    api_spec = Path(spec_file).read_text(encoding="UTF-8")
    api_spec = api_spec.replace("{{version}}", version)
    return jsonify(yaml.safe_load(api_spec)), 200


@general.route("/")
def metadata() -> Response:
    """Return corpus and lexicon metadata as a JSON object.

    Returns:
        A JSON object containing corpus and lexicon metadata.
    """
    resources_dict = utils.load_resources(
        current_app.config["RESOURCES"],
        Path(current_app.config["STATIC"]),
        cache_client=current_app.config.get("cache_client", None),
    )

    # Single resource was requested
    resource_id = request.args.get("resource")
    if resource_id:
        return jsonify(utils.get_single_resource(resource_id, resources_dict))

    # All data was requested
    return jsonify({key: utils.dict_to_list(value) for key, value in resources_dict.items()})


def create_resource_route(resource_type: str) -> None:
    """Create a route for the specified resource type.

    Args:
        resource_type: The type of resource to create a route for.
    """
    def resource() -> Response:
        """Return metadata for the specified resource type as a JSON object.

        Returns:
            A JSON object containing metadata for the specified resource type.
        """
        return jsonify(utils.get_resource_type(resource_type))

    general.add_url_rule(f"/{resource_type}", endpoint=f"{resource_type}", view_func=resource)


def create_routes() -> None:
    """Create routes for each resource type.

    This function is called by __init__.py when the app is created.
    """
    with current_app.app_context():
        for resource_type in current_app.config["RESOURCES"]:
            create_resource_route(resource_type)


@general.route("/collections")
def collections() -> Response:
    """Return collections metadata as a JSON object.

    Returns:
        A JSON object containing collections metadata.
    """
    collections = utils.load_json(
        Path(current_app.config["STATIC"]) / current_app.config["COLLECTIONS_FILE"],
        cache_client=current_app.config.get("cache_client", None),
    )
    data = utils.dict_to_list(collections)
    return jsonify({"hits": len(data), "resources": data})


@general.route("/list-ids")
def list_ids() -> list[str]:
    """List all existing resource IDs.

    Returns:
        A sorted list of all existing resource IDs.
    """
    resources = utils.load_resources(
        current_app.config["RESOURCES"],
        Path(current_app.config["STATIC"]),
        cache_client=current_app.config.get("cache_client", None),
    )
    resource_ids = [k for resource_type in resources.values() for k in resource_type]
    return sorted(resource_ids)


@general.route("/check-id-availability")
def check_id() -> tuple[Response, int]:
    """Check if a given resource ID is available.

    Returns:
        A JSON object indicating whether the resource ID is available.
    """
    input_id = request.args.get("id")
    if not input_id:
        return jsonify({"id": None, "error": "No ID provided"}), 400

    resources = utils.load_resources(
        current_app.config["RESOURCES"],
        Path(current_app.config["STATIC"]),
        cache_client=current_app.config.get("cache_client", None),
    )
    resource_ids = [k for resource_type in resources.values() for k in resource_type]
    if input_id in resource_ids:
        return jsonify({"id": input_id, "available": False}), 200
    return jsonify({"id": input_id, "available": True}), 200


@general.route("/renew-cache", methods=["GET", "POST"])
def renew_cache() -> tuple[Response, int]:
    """Trigger cache renewal as a background job."""
    # Parse resource_paths (may be overridden by GitHub webhook payload)
    resource_paths = request.args.get("resource-paths") or None
    resource_paths = resource_paths.split(",") if resource_paths else None
    debug = bool(request.args.get("debug")) or False
    offline = bool(request.args.get("offline")) or False

    try:
        logger.debug("Triggering cache renewal task.")
        # Enqueue the Celery task
        task = renew_cache_task.delay(
            request_method=request.method,
            resource_paths=resource_paths,
            static_path=str(current_app.config["STATIC"]),
            debug=debug,
            offline=offline,
        )
        logger.debug("Cache renewal task enqueued with task id: %s", task.id)
    except Exception as e:
        logger.exception("Error triggering cache renewal task: %s", e)
        return jsonify({"error": str(e), "message": "Failed to trigger cache renewal"}), 500

    # Return the task id so client can poll for status/results
    return jsonify({"task_id": task.id, "message": "Cache renewal triggered in background."}), 202


@general.route("/bibtex")
def bibtex() -> Response:
    """Return bibtex citation as text.

    Returns:
        A JSON object containing the bibtex citation.
    """
    try:
        resource_id = request.args.get("resource")
        if resource_id:
            resources_dict = utils.load_resources(
                current_app.config["RESOURCES"],
                Path(current_app.config["STATIC"]),
                cache_client=current_app.config.get("cache_client", None),
            )
            bibtex = utils.get_bibtex(resource_id, resources_dict)
        else:
            bibtex = "Error: Incorrect arguments provided. Format: /bibtex?resource=<id>"
    except Exception as e:
        bibtex = f"Error when creating bibtex: {e!s}"

    return jsonify({"bibtex": bibtex})


@general.route("/schema")
def schema() -> Response:
    """Return JSON schema for the metadata.

    Returns:
        A JSON object containing the JSON schema.
    """
    schema_file = Path(current_app.config["METADATA_DIR"]) / current_app.config["SCHEMA_FILE"]
    schema = json.loads(schema_file.read_text(encoding="UTF-8"))
    schema = adapt_schema(schema)
    return jsonify(schema)
