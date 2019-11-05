"""Collection of routes."""

import os
import locale

from flask import current_app, jsonify, Blueprint
import json

general = Blueprint("general", __name__)
locale.setlocale(locale.LC_ALL, "sv_SE.utf8")


@general.route("/")
def metadata():
    """Return corpus and lexicon meta data as a JSON object."""
    corpora = dict_to_list(read_static_json(current_app.config.get("CORPORA_FILE")))
    lexicons = dict_to_list(read_static_json(current_app.config.get("LEXICONS_FILE")))

    metadata = {"corpora": corpora, "lexicons": lexicons}
    return jsonify(metadata)


def read_static_json(jsonfile):
    """Load json file from static folder and return as object."""
    file_path = os.path.join(current_app.config.get("STATIC"), jsonfile)
    with open(file_path, "r") as f:
        return json.load(f)


def dict_to_list(input):
    """Convert resource dict into list, sorted by name_sv."""
    return sorted(input.values(), key=lambda x: locale.strxfrm(x.get("name_sv")))
