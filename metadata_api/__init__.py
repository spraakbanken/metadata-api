"""Instanciation of flask app."""

from pathlib import Path

from flask import Flask
from flask_cors import CORS

from . import views

try:
    from pymemcache import serde
    from pymemcache.client.base import Client
except ImportError:
    print("Could not load pymemcache. Caching will be disabled.")
    no_memcache = True
else:
    no_memcache = False


def create_app() -> Flask:
    """Instanciate app."""
    app = Flask(__name__)
    CORS(app)

    # Read config
    app.config.from_object("config")

    # Set static path
    app.config["STATIC"] = Path(app.root_path) / "static"

    # Prevent flask from resorting JSON
    app.config["JSON_SORT_KEYS"] = False

    # Connect to memcached if possible
    no_cache = no_memcache
    if not no_memcache:
        no_cache = app.config.get("NO_CACHE", False)
    app.config["NO_CACHE"] = no_cache
    if not no_cache:
        try:
            app.config["cache_client"] = Client(
                (app.config["MEMCACHED_HOST"], app.config["MEMCACHED_PORT"]), serde=serde.pickle_serde
            )
            mc = app.config.get("cache_client")
            mc.set("test_key", "test_value")
            mc.get("test_key", "test_value")
        except Exception as e:
            print(f"Error initializing memcache client: {e}")

    # Create resource routes for resource types defined in the config ("RESOURCES")
    with app.app_context():
        views.create_routes()

    app.register_blueprint(views.general)

    return app
