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
    corpora, lexicons, models, analyses, utilities = utils.load_resources()

    resource = request.args.get("resource")
    if resource:
        return utils.get_single_resource(resource, corpora, lexicons, models, analyses, utilities)

    data = {
        "corpora": utils.dict_to_list(corpora),
        "lexicons": utils.dict_to_list(lexicons),
        "models": utils.dict_to_list(models),
        "analyses": utils.dict_to_list(analyses),
        "utilities": utils.dict_to_list(utilities),
    }

    return jsonify(data)


@general.route("/corpora")
def corpora() -> Response:
    """Return corpus metadata as a JSON object.

    Returns:
        A JSON object containing corpus metadata.
    """
    return utils.get_resource_type("corpus", "CORPORA_FILE")


@general.route("/lexicons")
def lexicons() -> Response:
    """Return lexicon metadata as a JSON object.

    Returns:
        A JSON object containing lexicon metadata.
    """
    return utils.get_resource_type("lexicon", "LEXICONS_FILE")


@general.route("/models")
def models() -> Response:
    """Return models metadata as a JSON object.

    Returns:
        A JSON object containing models metadata.
    """
    return utils.get_resource_type("model", "MODELS_FILE")


@general.route("/analyses")
def analyses() -> Response:
    """Return analyses metadata as a JSON object.

    Returns:
        A JSON object containing analyses metadata.
    """
    return utils.get_resource_type("analysis", "ANALYSES_FILE")


@general.route("/utilities")
def utilities() -> Response:
    """Return utilities metadata as a JSON object.

    Returns:
        A JSON object containing utilities metadata.
    """
    return utils.get_resource_type("utilities", "UTILITIES_FILE")


@general.route("/collections")
def collections() -> Response:
    """Return collections metadata as a JSON object.

    Returns:
        A JSON object containing collections metadata.
    """
    corpora, lexicons, models, analyses, utilities = utils.load_resources()

    data = {name: data for (name, data) in corpora.items() if data.get("collection")}
    lexicons = {name: data for (name, data) in lexicons.items() if data.get("collection")}
    data.update(lexicons)
    models = {name: data for (name, data) in models.items() if data.get("collection")}
    data.update(models)
    analyses = {name: data for (name, data) in models.items() if data.get("collection")}
    data.update(analyses)
    utilities = {name: data for (name, data) in models.items() if data.get("collection")}
    data.update(utilities)

    return jsonify({"hits": len(data), "resources": utils.dict_to_list(data)})


@general.route("/list-ids")
def list_ids() -> list[str]:
    """List all existing resource IDs.

    Returns:
        A sorted list of all existing resource IDs.
    """
    resource_ids = [k for res_type in utils.load_resources() for k in list(res_type.keys())]
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
    resource_ids = {k for res_type in utils.load_resources() for k in list(res_type.keys())}
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
        res_id = request.args.get("resource")
        if res_id:
            corpora, lexicons, models, analyses, utilities = utils.load_resources()
            bibtex = utils.get_bibtex(res_id, corpora, lexicons, models, analyses, utilities)
        else:
            bibtex = "Error: Incorrect arguments provided. Format: /bibtex?type=<>&resource=<id>"
    except Exception as e:
        bibtex = f"Error when creating bibtex: {e!s}"

    return jsonify({"bibtex": bibtex})
