"""Routes for the metadata API."""

# import locale

from flask import Blueprint, current_app, jsonify, request
from . import utils

general = Blueprint("general", __name__)
# locale.setlocale(locale.LC_ALL, "sv_SE.utf8")


@general.route("/doc")
def documentation():
    """Serve API documentation yaml file."""
    return current_app.send_static_file("apidoc.yaml")


@general.route("/")
def metadata():
    """Return corpus and lexicon metadata as a JSON object."""
    resource = request.args.get("resource")
    if resource:
        corpora = utils.load_data(current_app.config.get("CORPORA_FILE"))
        lexicons = utils.load_data(current_app.config.get("LEXICONS_FILE"))
        models = utils.load_data(current_app.config.get("MODELS_FILE"))
        return utils.get_single_resource(resource, corpora, lexicons, models)

    remove_keys = current_app.config.get("HIDE_FROM_LISTING")
    corpora = utils.load_data(current_app.config.get("CORPORA_FILE"), remove_keys=remove_keys)
    lexicons = utils.load_data(current_app.config.get("LEXICONS_FILE"), remove_keys=remove_keys)
    models = utils.load_data(current_app.config.get("MODELS_FILE"), remove_keys=remove_keys)
    data = {"corpora": utils.dict_to_list(corpora), "lexicons": utils.dict_to_list(lexicons),
            "models": utils.dict_to_list(models)}

    return jsonify(data)


@general.route("/corpora")
def corpora():
    """Return corpus metadata as a JSON object."""
    json_data = utils.get_resource_type("corpus", "CORPORA_FILE")
    return json_data


@general.route("/lexicons")
def lexicons():
    """Return lexicon metadata as a JSON object."""
    json_data = utils.get_resource_type("lexicon", "LEXICONS_FILE")
    return json_data


@general.route("/models")
def models():
    """Return models metadata as a JSON object."""
    json_data = utils.get_resource_type("model", "MODELS_FILE")
    return json_data


@general.route("/collections")
def collections():
    """Return collections metadata as a JSON object."""
    remove_keys = current_app.config.get("HIDE_FROM_LISTING")
    corpora = utils.load_data(current_app.config.get("CORPORA_FILE"), remove_keys=remove_keys)
    data = dict([(name, data) for (name, data) in corpora.items() if data.get("collection")])

    lexicons = utils.load_data(current_app.config.get("LEXICONS_FILE"), remove_keys=remove_keys)
    lexicons = dict([(name, data) for (name, data) in lexicons.items() if data.get("collection")])
    data.update(lexicons)

    models = utils.load_data(current_app.config.get("MODELS_FILE"), remove_keys=remove_keys)
    models = dict([(name, data) for (name, data) in models.items() if data.get("collection")])
    data.update(models)

    return jsonify({
        "hits": len(data),
        "resources": utils.dict_to_list(data)
    })


@general.route("/renew-cache")
def renew_cache():
    """Flush cache and re-read json files."""
    try:
        if not current_app.config.get("NO_CACHE"):
            mc = current_app.config.get("cache_client")
            mc.flush_all()
        utils.load_data(current_app.config.get("CORPORA_FILE"))
        utils.load_data(current_app.config.get("LEXICONS_FILE"))
        utils.load_data(current_app.config.get("MODELS_FILE"))
        utils.load_data(current_app.config.get("RESOURCE_TEXTS_FILE"), prefix="res_desc")
        success = True
        error = None
    except Exception:
        success = False
    return jsonify({"cache_renewed": success,
                    "error": error})
