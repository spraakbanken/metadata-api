"""Run the FastAPI development server.

Will run with the following defaults:
 - server: localhost:8000
 - ENV=development
 - LOG_LEVEL=DEBUG
 - LOG_TO_FILE=False (logging to console only)
 - reload is enabled (for automatic server restarts on code changes)

Usage:
    python run.py [--host HOST] [--port PORT]
"""

import argparse
import logging
import os

import uvicorn


def main() -> None:
    """Run the FastAPI development server."""
    parser = argparse.ArgumentParser(description="Run the FastAPI development server on localhost.")
    parser.add_argument("--host", "-H", default="127.0.0.1", help="Host to bind (default: 127.0.0.1)")
    parser.add_argument("--port", "-p", type=int, default=8000, help="Port to run the server on (default: 8000)")
    parser.add_argument("--log-level", "-l", default="DEBUG", help="Logging level (default: DEBUG)")
    args = parser.parse_args()

    # Suppress some chatty logs
    logging.getLogger("watchfiles.main").setLevel("WARNING")

    # Ensure dev-friendly settings are in place before the app is imported.
    os.environ.setdefault("ENV", "development")
    os.environ.setdefault("LOG_LEVEL", args.log_level)
    os.environ.setdefault("LOG_TO_FILE", "False")

    uvicorn.run(
        "metadata_api.main:app",
        host=args.host,
        port=args.port,
        reload=True,
        reload_dirs=["."],
        reload_includes=[
            ".env",
            "metadata_api/*.py",
            "metadata_api/static/*",
            "docs/mkdocs/index.md",
            "docs/dev-docs.md",
            "docs/pid_guide.md",
            "README.md",
            "CHANGELOG.md",
        ],
        reload_excludes=[
            "run.py",
            "metadata_api/static/*.json",
            "tests/*.py",
            "docs/site/*",
            "docs/site/**/*",
            "**/__pycache__/*",
            "metadata_api/__pycache__",
            "**/*.pyc",
            "**/*.pyo",
        ],
        log_level=args.log_level.lower(),
    )


if __name__ == "__main__":
    main()
