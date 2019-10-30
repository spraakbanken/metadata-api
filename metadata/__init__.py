"""Instanciation of flask app."""

import os

from flask import Flask


def create_app():
    """Instanciate app."""
    app = Flask(__name__)

    # Read config
    app.config.from_object('config')

    # Set static path
    app.config["STATIC"] = os.path.join(app.root_path, "static")

    # Prevent flask from resorting JSON
    app.config['JSON_SORT_KEYS'] = False

    from . import views
    app.register_blueprint(views.general)

    return app
