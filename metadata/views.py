"""Collection of routes."""

import json
import locale
import os

from flask import Blueprint, current_app, jsonify, request

from .blacklist import BLACKLIST

general = Blueprint("general", __name__)
locale.setlocale(locale.LC_ALL, "sv_SE.utf8")


@general.route("/")
def metadata():
    """Return corpus and lexicon meta data as a JSON object."""
    corpora = read_static_json(current_app.config.get("CORPORA_FILE"))
    lexicons = read_static_json(current_app.config.get("LEXICONS_FILE"))

    resource = request.args.get("resource")
    if resource:
        return get_single_resource(resource, corpora, lexicons)

    metadata = {"corpora": dict_to_list(corpora), "lexicons": dict_to_list(lexicons)}

    has_description = True if (request.args.get("has-description", "")).lower() == "true" else False
    if has_description:
        metadata = {
            "corpora": [c for c in metadata["corpora"] if c["has_description"]],
            "lexicons": [c for c in metadata["lexicons"] if c["has_description"]]
        }

    return jsonify(metadata)


@general.route("/doc")
def documentation():
    """Serve API documentation yaml file."""
    return current_app.send_static_file('apidoc.yaml')


def get_single_resource(resource_id, corpora, lexicons):
    """Get lexicon or corpus from resource dictionaries and add resource text (if available)."""
    resource_texts = read_static_json(current_app.config.get("RESOURCE_TEXTS_FILE"))
    long_description = resource_texts.get(resource_id, {})

    if corpora.get(resource_id):
        resource = corpora[resource_id]
        resource["long_description_sv"] = long_description.get("sv", "")
        resource["long_description_en"] = long_description.get("en", "")
    elif lexicons.get(resource_id):
        resource = lexicons[resource_id]
        resource["long_description_sv"] = long_description.get("sv", "")
        resource["long_description_en"] = long_description.get("en", "")
    else:
        resource = {}

    return jsonify(resource)


def read_static_json(jsonfile):
    """Load json file from static folder and return as object."""
    file_path = os.path.join(current_app.config.get("STATIC"), jsonfile)
    with open(file_path, "r") as f:
        return json.load(f)


def dict_to_list(input):
    """Convert resource dict into list."""
    # return sorted(input.values(), key=lambda x: locale.strxfrm(x.get("name_sv")))
    return list(input.values())
