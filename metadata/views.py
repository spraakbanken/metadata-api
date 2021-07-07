"""Collection of routes."""

import json
# import locale
import os

from flask import Blueprint, current_app, jsonify, request

general = Blueprint("general", __name__)
# locale.setlocale(locale.LC_ALL, "sv_SE.utf8")


@general.route("/")
def metadata():
    """Return corpus and lexicon metadata as a JSON object."""
    corpora = load_data(current_app.config.get("CORPORA_FILE"))
    lexicons = load_data(current_app.config.get("LEXICONS_FILE"))
    models = load_data(current_app.config.get("MODELS_FILE"))

    resource = request.args.get("resource")
    if resource:
        return get_single_resource(resource, corpora, lexicons, models)

    data = {"corpora": dict_to_list(corpora), "lexicons": dict_to_list(lexicons),
            "models": dict_to_list(models)}

    has_description = True if (request.args.get("has-description", "")).lower() == "true" else False
    if has_description:
        data = {
            "corpora": [c for c in data["corpora"] if c["has_description"]],
            "lexicons": [c for c in data["lexicons"] if c["has_description"]],
            "models": [c for c in data["models"] if c["has_description"]]
        }

    return jsonify(data)


@general.route("/corpora")
def corpora():
    """Return corpus metadata as a JSON object."""
    has_description = True if (request.args.get("has-description", "")).lower() == "true" else False
    json_data = get_resource_type("corpus", "CORPORA_FILE", only_with_description=has_description)
    return json_data


@general.route("/lexicons")
def lexicons():
    """Return lexicon metadata as a JSON object."""
    has_description = True if (request.args.get("has-description", "")).lower() == "true" else False
    json_data = get_resource_type("lexicon", "LEXICONS_FILE", only_with_description=has_description)
    return json_data


@general.route("/models")
def models():
    """Return models metadata as a JSON object."""
    has_description = True if (request.args.get("has-description", "")).lower() == "true" else False
    json_data = get_resource_type("model", "MODELS_FILE", only_with_description=has_description)
    return json_data


@general.route("/renew-cache")
def renew_cache():
    """Flush cache and re-read json files."""
    try:
        if not current_app.config.get("NO_CACHE"):
            mc = current_app.config.get("cache_client")
            mc.flush_all()
        load_data(current_app.config.get("CORPORA_FILE"))
        load_data(current_app.config.get("LEXICONS_FILE"))
        load_data(current_app.config.get("MODELS_FILE"))
        load_data(current_app.config.get("RESOURCE_TEXTS_FILE"), prefix="res_desc")
        success = True
        error = None
    except Exception:
        success = False
    return jsonify({"cache_renewed": success,
                    "error": error})


@general.route("/doc")
def documentation():
    """Serve API documentation yaml file."""
    return current_app.send_static_file("apidoc.yaml")


def get_single_resource(resource_id, corpora, lexicons, models):
    """Get lexicon or corpus from resource dictionaries and add resource text (if available)."""
    resource_texts = load_data(current_app.config.get("RESOURCE_TEXTS_FILE"), prefix="res_desc")
    long_description = resource_texts.get(resource_id, {})

    resource = {}
    if corpora.get(resource_id):
        resource = corpora[resource_id]
    elif lexicons.get(resource_id):
        resource = lexicons[resource_id]
    elif models.get(resource_id):
        resource = models[resource_id]

    if resource:
        resource["long_description_sv"] = long_description.get("sv", "")
        resource["long_description_en"] = long_description.get("en", "")

    return jsonify(resource)


def load_data(jsonfile, prefix=""):
    """Load data from cache."""
    if current_app.config.get("NO_CACHE"):
        return read_static_json(jsonfile)
    mc = current_app.config.get("cache_client")
    data = mc.get(add_prefix(jsonfile, prefix))
    if not data:
        all_data = read_static_json(jsonfile)
        mc.set(add_prefix(jsonfile, prefix), list(all_data.keys()))
        for k, v in all_data.items():
            mc.set(add_prefix(k, prefix), v)
    else:
        all_data = {}
        for k in data:
            all_data[k] = mc.get(add_prefix(k, prefix))
    return all_data


def read_static_json(jsonfile):
    """Load json file from static folder and return as object."""
    print("Reading json", jsonfile)
    file_path = os.path.join(current_app.config.get("STATIC"), jsonfile)
    with open(file_path, "r") as f:
        return json.load(f)


def add_prefix(key, prefix):
    """Add prefix to key."""
    if prefix:
        key = "{}_{}".format(prefix, key)
    return key


def dict_to_list(input_obj):
    """Convert resource dict into list."""
    # return sorted(input.values(), key=lambda x: locale.strxfrm(x.get("name_sv")))
    return list(input_obj.values())


def get_resource_type(rtype, resource_file, only_with_description=False):
    """Get list of resources of one resource type."""
    resource_type = load_data(current_app.config.get(resource_file))
    data = dict_to_list(resource_type)

    if only_with_description:
        data = [c for c in data if c["has_description"]]

    return jsonify({
        "resource_type": rtype,
        "hits": len(data),
        "resources": data
    })
