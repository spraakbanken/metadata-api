"""Collection of routes."""

import os

from flask import current_app, jsonify, Blueprint
import json

general = Blueprint("general", __name__)


@general.route("/")
def metadata():
    """Return corpus and lexicon meta data as a JSON object."""
    corpora = read_static_json(current_app.config.get("CORPORA_FILE"))
    lexicons = read_static_json(current_app.config.get("LEXICONS_FILE"))

    metadata = corpora
    metadata.update(lexicons)


    return jsonify(metadata)


def read_static_json(jsonfile):
    """Load json file from static folder and return as object."""
    file_path = os.path.join(current_app.config.get("STATIC"), jsonfile)
    with open(file_path, "r") as f:
        return json.load(f)
