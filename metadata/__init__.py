"""Instanciation of flask app."""

import os

from flask import Flask
from flask_cors import CORS

try:
    import memcache
except ImportError:
    print("Could not load memcache. Caching will be disabled.")
    no_memcache = True
else:
    no_memcache = False


def create_app():
    """Instanciate app."""
    app = Flask(__name__)
    CORS(app)

    # Read config
    app.config.from_object("config")

    # Set static path
    app.config["STATIC"] = os.path.join(app.root_path, "static")

    # Prevent flask from resorting JSON
    app.config["JSON_SORT_KEYS"] = False

    # Connect to memcached if possible
    no_cache = no_memcache
    if not no_memcache:
        no_cache = app.config.get("NO_CACHE", False)
    app.config["NO_CACHE"] = no_cache
    if not no_cache:
        app.config["cache_client"] = memcache.Client([(app.config["MEMCACHED_HOST"], app.config["MEMCACHED_PORT"])])

    from . import views
    app.register_blueprint(views.general)

    return app
