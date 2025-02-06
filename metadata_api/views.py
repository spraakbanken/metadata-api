"""Routes for the metadata API."""

from flask import Blueprint, Response, current_app, jsonify, request

from . import utils

general = Blueprint("general", __name__)


@general.route("/doc")
def documentation() -> Response:
    """Serve API documentation yaml file.

    Returns:
        The API documentation file.
    """
    return current_app.send_static_file("apidoc.yaml")


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

    Returns:
        A JSON object indicating whether the cache was successfully renewed.
    """
    try:
        if not current_app.config.get("NO_CACHE"):
            mc = current_app.config.get("cache_client")
            mc.flush_all()
        utils.load_resources()
        utils.load_json(current_app.config.get("RESOURCE_TEXTS_FILE"), prefix="res_desc")
        success = True
        error = None
    except Exception:
        success = False
    return jsonify({"cache_renewed": success, "error": error})


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
    schema = utils.load_json(current_app.config.get("SCHEMA_FILE"))
    return jsonify(schema)
