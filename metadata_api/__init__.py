"""Instanciation of flask app."""

import logging
from datetime import datetime
from pathlib import Path

from flask import Flask
from flask_cors import CORS

from . import views

logger = logging.getLogger(__name__)

try:
    from pymemcache import serde
    from pymemcache.client.base import Client
except ImportError:
    logger.warning("Could not load pymemcache. Caching will be disabled.")
    no_memcache = True
else:
    no_memcache = False


def create_app(log_to_stdout: bool = False) -> Flask:
    """Instanciate app.

    Args:
        log_to_stdout: Whether to log to stdout.

    Returns:
        The Flask app instance.
    """
    app = Flask(__name__)
    CORS(app)

    # Read config
    app.config.from_object("config")

    # Create log directory if it does not exist
    log_dir = Path(app.config["LOG_DIR"])
    log_dir.mkdir(parents=True, exist_ok=True)

    # Configure logger
    if log_to_stdout:
        logging.basicConfig(level=app.config["LOG_LEVEL"], format=app.config["LOG_FORMAT"])
    else:
        log_filename = log_dir / f"metadata_api_{datetime.now().strftime('%Y-%m-%d')}.log"
        logging.basicConfig(
            level=app.config["LOG_LEVEL"],
            format=app.config["LOG_FORMAT"],
            handlers=[
                logging.FileHandler(log_filename),
                logging.StreamHandler()
            ]
        )

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
            mc.get("test_key")
        except Exception:
            logger.exception("Error initializing memcache client")

    # Create resource routes for resource types defined in the config ("RESOURCES")
    with app.app_context():
        views.create_routes()

    app.register_blueprint(views.general)

    return app
