"""Instanciation of flask app."""

import logging
import traceback
from datetime import datetime
from pathlib import Path

from flask import Flask, Response, jsonify, request
from flask_cors import CORS

from . import views
from .memcached import cache

logger = logging.getLogger(__name__)


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
    app.config.from_object("config_default")
    config_path = Path(app.root_path).parent / "config.py"
    if config_path.exists():
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

    logger.info("Starting metadata API")

    # Log warning if no config file is found
    if not config_path.exists():
        logger.warning("No 'config.py' found. Using default configuration from 'config_default.py'.")

    # Set static path
    app.config["STATIC"] = Path(app.root_path) / "static"

    # Prevent flask from resorting JSON
    app.config["JSON_SORT_KEYS"] = False

    # Set celery log level to INFO to reduce verbosity
    logging.getLogger("celery").setLevel(logging.INFO)
    logging.getLogger("celery.app.trace").setLevel(logging.INFO)

    # Initialize memcached client
    cache.initialize(app.config["MEMCACHED_SERVER"])

    # Create resource routes for resource types defined in the config
    views.create_routes(list(app.config["RESOURCES"].keys()))

    app.register_blueprint(views.general)

    @app.before_request
    def log_request_info() -> None:
        """Print some info about the incoming request."""
        if request.method != "OPTIONS":
            app.logger.info("Request: %s %s", request.method, request.url)

    @app.errorhandler(400)
    def handle_400_error(error: Exception) -> tuple[Response, int]:
        """Handle bad request errors."""
        logger.warning("Bad Request: %s", error)
        return jsonify({"Error": "Bad Request"}), 400

    @app.errorhandler(404)
    def handle_404_error(error: Exception) -> tuple[Response, int]:
        """Handle not found errors."""
        logger.warning("Not Found: %s", error)
        return jsonify({"Error": "Not Found"}), 404

    @app.errorhandler(500)
    def handle_500_error(error: Exception) -> tuple[Response, int]:
        """Handle internal server errors."""
        tb = traceback.format_exc()
        logger.error("Server Error: %s\nTraceback: %s", error, tb)
        return jsonify({"Error": "Internal Server Error", "traceback": tb}), 500

    return app
