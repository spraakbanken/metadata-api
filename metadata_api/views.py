"""Routes for the metadata API."""

import io
import json
import logging
from pathlib import Path

import yaml
from flask import Blueprint, Response, current_app, jsonify, request
from git import Repo

from . import utils
from .adapt_schema import adapt_schema
from .parse_yaml import logger as parse_yaml_logger
from .parse_yaml import process_resources

general = Blueprint("general", __name__)
logger = logging.getLogger(__name__)
version = utils.get_version_from_pyproject()


@general.route("/doc")
def documentation() -> Response:
    """Serve API documentation as json data.

    Returns:
        The API documentation as a json response.
    """
    spec_file = Path(current_app.static_folder) / "apidoc.yaml"
    api_spec = Path(spec_file).read_text(encoding="UTF-8")
    api_spec = api_spec.replace("{{version}}", version)
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
    collections = utils.load_json(current_app.config.get("COLLECTIONS_FILE"))
    data = utils.dict_to_list(collections)
    return jsonify({"hits": len(data), "resources": data})


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


@general.route("/renew-cache", methods=["GET", "POST"])
def renew_cache() -> Response:
    """Update metadata files from git, re-process json files and update cache.

    API arguments:
        resource-paths: Path to specific resources to parse and update (<resource_type/resource_id>).
        debug: Print debug info while parsing YAML files.
        offline: Skip getting file info for downloadables when parsing YAML files.

    Returns:
        A JSON object indicating whether the cache was successfully renewed.
    """
    resource_paths = request.args.get("resource-paths") or None
    debug = request.args.get("debug") or False
    offline = request.args.get("offline") or False

    # Pull changes from GitHub before parsing YAML files
    try:
        repo = Repo(current_app.config.get("METADATA_DIR"))
        repo.remotes.origin.pull()
    except Exception as e:
        msg = f"Error when pulling changes from GitHub: {e}"
        logger.error(msg)
        utils.send_to_slack(msg)
        return jsonify({"cache_renewed": False, "errors": [msg], "warnings": [], "info": []}), 500

    # Parse POST request payload from GitHub webhook
    if request.method == "POST":
        try:
            payload = request.get_json()
            logger.debug("GitHub payload: %s", payload)
            if payload:
                # Check if the webhook was triggered on the main branch
                if payload.get("ref", "") != "refs/heads/main":
                    msg = "GitHub webhook triggered, but not on main branch. Nothing to do."
                    logger.info(msg)
                    return jsonify({"cache_renewed": False, "errors": [], "warnings": [msg], "info": []}), 200
                # Check if payload contains a list of changed files
                changed_files = []
                git_commits = payload.get("commits", [])
                if not git_commits:
                    msg = f"No commits detected in payload.\nPayload:\n{payload}"
                    logger.error(msg)
                    utils.send_to_slack(msg)
                    return jsonify({"cache_renewed": False, "errors": [msg], "warnings": [], "info": []}), 400
                for commit in git_commits:
                    changed_files.extend(commit.get("added", []))
                    changed_files.extend(commit.get("modified", []))
                    changed_files.extend(commit.get("removed", []))

                # If too many files were changed, GitHub will not provide a complete list. Update all data in this case.
                file_limit = current_app.config.get("GITHUB_FILE_LIMIT")
                if len(changed_files) > file_limit:
                    resource_paths = None
                # Format paths (strip first component and file ending) to create input for process_resources
                else:
                    resource_paths = []
                    for p in changed_files:
                        # Only process resource metadata YAML files
                        if Path(p).parts[0] == "yaml" and Path(p).suffix == ".yaml":
                            resource_paths.append(str(Path(*Path(p).parts[1:-1]) / Path(p).stem))

        except Exception as e:
            msg = f"Error when parsing GitHub payload: {e}.\nPayload:\n{payload}"
            logger.error(msg)
            utils.send_to_slack(msg)
            return jsonify({"cache_renewed": False, "errors": [str(e)], "warnings": [], "info": []}), 500

    # Parse resource_paths from GET request
    elif request.method == "GET" and resource_paths:
        resource_paths = resource_paths.split(",")

    # Create a string buffer to capture logs from process_resources
    log_capture_string = io.StringIO()
    log_handler = logging.StreamHandler(log_capture_string)
    log_handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    parse_yaml_logger.addHandler(log_handler)
    errors = []
    warnings = []
    info = []

    try:
        # Update data and rebuild all JSON files (reprocess all data if resource_paths is None)
        process_resources(
            resource_paths=resource_paths, config_obj=current_app.config, validate=True, debug=debug, offline=offline
        )

        if not current_app.config.get("NO_CACHE"):
            mc = current_app.config.get("cache_client")
            mc.flush_all()
        # Reload resources and resource texts to populate cache
        utils.load_resources()
        utils.load_json(current_app.config.get("RESOURCE_TEXTS_FILE"), prefix="res_descr")
        utils.load_json(current_app.config.get("COLLECTIONS_FILE"))
        success = True

    except Exception as e:
        success = False
        errors = [str(e)]

    # Get the process_resources logs from the string buffer
    log_messages = log_capture_string.getvalue().splitlines()
    log_capture_string.close()
    parse_yaml_logger.removeHandler(log_handler)

    # Sort log messages into errors, warnings, and info/other
    for message in log_messages:
        if message.startswith(("ERROR", "CRITICAL")):
            errors.append(message)
        elif message.startswith("WARNING"):
            warnings.append(message)
        else:
            info.append(message)
    logger.info("Cache renewal completed.")

    if errors or warnings:
        utils.send_to_slack("Cache renewal completed.\n" + "\n".join(errors + warnings))

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
    schema = adapt_schema(schema)
    return jsonify(schema)
