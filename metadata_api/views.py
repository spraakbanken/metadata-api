"""Routes for the metadata API."""

import io
import json
import logging
from pathlib import Path

import yaml
from flask import Blueprint, Response, current_app, jsonify, request

from . import __version__, utils
from .parse_yaml import logger as parse_yaml_logger
from .parse_yaml import main as parse_yaml

general = Blueprint("general", __name__)


@general.route("/doc")
def documentation() -> Response:
    """Serve API documentation as json data.

    Returns:
        The API documentation as a json response.
    """
    spec_file = Path(current_app.static_folder) / "apidoc.yaml"
    api_spec = Path(spec_file).read_text(encoding="UTF-8")
    api_spec = api_spec.replace("{{version}}", __version__)
    return jsonify(yaml.safe_load(api_spec))


@general.route("/")
def metadata() -> Response:
    """Return corpus and lexicon metadata as a JSON object.

    Returns:
        A JSON object containing corpus and lexicon metadata.
    """
    resources_dict = utils.load_resources()

    # Single resource was requested
    resource_id = request.args.get("resource")
    if resource_id:
        return utils.get_single_resource(resource_id, resources_dict)

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
        return utils.get_resource_type(resource_type)

    general.add_url_rule(f"/{resource_type}", endpoint=f"{resource_type}", view_func=resource)


def create_routes() -> None:
    """Create routes for each resource type.

    This function is called by __init__.py when the app is created.
    """
    with current_app.app_context():
        for resource_type in current_app.config.get("RESOURCES"):
            create_resource_route(resource_type)


@general.route("/collections")
def collections() -> Response:
    """Return collections metadata as a JSON object.

    Returns:
        A JSON object containing collections metadata.
    """
    resources_dict = utils.load_resources()

    data = {}
    for resource_type in resources_dict:
        data.update(
            {
                resource_id: resource
                for resource_id, resource in resources_dict[resource_type].items()
                if resource.get("collection")
            }
        )

    return jsonify({"hits": len(data), "resources": utils.dict_to_list(data)})


@general.route("/list-ids")
def list_ids() -> list[str]:
    """List all existing resource IDs.

    Returns:
        A sorted list of all existing resource IDs.
    """
    resource_ids = [k for resource_type in utils.load_resources().values() for k in resource_type]
    return sorted(resource_ids)


@general.route("/check-id-availability")
def check_id() -> Response:
    """Check if a given resource ID is available.

    Returns:
        A JSON object indicating whether the resource ID is available.
    """
    input_id = request.args.get("id")
    if not input_id:
        return jsonify({"id": None, "error": "No ID provided"})
    resource_ids = [k for resource_type in utils.load_resources().values() for k in resource_type]
    if input_id in resource_ids:
        return jsonify({"id": input_id, "available": False})
    return jsonify({"id": input_id, "available": True})


@general.route("/renew-cache")
def renew_cache() -> Response:
    """Flush cache and re-read json files.

    API arguments:
        resource-paths: Path to specific resource to parse and update (<resource_type/resource_id>).
        debug: Print debug info while parsing YAML files.
        offline: Skip getting file info for downloadables when parsing YAML files.

    Returns:
        A JSON object indicating whether the cache was successfully renewed.
    """
    debug = request.args.get("debug") or False
    offline = request.args.get("offline") or False

    # Create a string buffer to capture logs from parse_yaml
    log_capture_string = io.StringIO()
    log_handler = logging.StreamHandler(log_capture_string)
    log_handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    if debug:
        log_handler.setLevel(logging.DEBUG)
    else:
        log_handler.setLevel(logging.INFO)
    parse_yaml_logger.addHandler(log_handler)
    errors = []
    warnings = []
    info = []

    try:
        resource_paths = request.args.get("resource-paths") or None
        if resource_paths:
            resource_paths = resource_paths.split(",")
        # Update all data and rebuild all JSON files, alternatively update only data for a specific resource
        parse_yaml(
            resource_paths=resource_paths, config_obj=current_app.config, validate=True, debug=debug, offline=offline
        )

        if not current_app.config.get("NO_CACHE"):
            mc = current_app.config.get("cache_client")
            mc.flush_all()
        utils.load_resources()
        utils.load_json(current_app.config.get("RESOURCE_TEXTS_FILE"), prefix="res_descr")
        success = True

    except Exception as e:
        success = False
        errors = [str(e)]

    # Get the parse_yaml logs from the string buffer
    log_contents = log_capture_string.getvalue()
    log_capture_string.close()
    parse_yaml_logger.removeHandler(log_handler)
    log_messages = log_contents.splitlines()

    # Sort log messages into errors, warnings, and info/other
    for message in log_messages:
        if message.startswith(("ERROR", "CRITICAL")):
            errors.append(message)
        elif message.startswith("WARNING"):
            warnings.append(message)
        else:
            info.append(message)

    return jsonify({"cache_renewed": success, "errors": errors, "warnings": warnings, "info": info})


@general.route("/bibtex")
def bibtex() -> Response:
    """Return bibtex citation as text.

    Returns:
        A JSON object containing the bibtex citation.
    """
    try:
        resource_id = request.args.get("resource")
        if resource_id:
            resources_dict = utils.load_resources()
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
    schema_file = Path(current_app.config.get("METADATA_DIR")) / current_app.config.get("SCHEMA_FILE")
    schema = json.loads(schema_file.read_text(encoding="UTF-8"))
    return jsonify(schema)
