# Språkbanken Text Metadata API

The Språkbanken Text Metadata API is a RESTful web service that provides access to metadata for various resources
maintained by Språkbanken Text, including corpora, lexicons, models, analyses, and utilities. The metadata is stored in
YAML files in a separate [metadata repository](https://github.com/spraakbanken/metadata).

For more technical details, see the [developer documentation](https://ws.spraakbanken.gu.se/ws/metadata/v3/docs/).

## Basic API Usage

Available API calls (please note that the URL contains the API version, e.g. `/v3`, `/dev` etc):

| Endpoint | Description |
| -------- | ----------- |
| 📁 [/](https://ws.spraakbanken.gu.se/ws/metadata/v3/) | List all resources |
| 📁 [/?resource-type=[resource-type]](https://ws.spraakbanken.gu.se/ws/metadata/v3/?resource-type=corpus) | List all resources of a specific type.<br>Available types: `corpus`, `lexicon`, `model`, `analysis`, `utility`, `collection` |
| 📁 [/list-ids](https://ws.spraakbanken.gu.se/ws/metadata/v3/list-ids) | List all existing resource IDs |
| 🔍 [/?resource=saldo](https://ws.spraakbanken.gu.se/ws/metadata/v3/?resource=saldo) | Retrieve a specific resource and its description (if available) |
| 🔍 [/bibtex?resource=[resource-id]](https://ws.spraakbanken.gu.se/ws/metadata/v3/bibtex?resource=attasidor) | Return BibTeX citation for the specified resource |
| 🔍 [/source/[resource_type]/[resource-id]](https://ws.spraakbanken.gu.se/ws/metadata/v3/source/corpus/attasidor) | Retrieve the source metadata for a resource (without applying metadata processing) |
| 🔍 [/check-id-availability?id=[resource-id]](https://ws.spraakbanken.gu.se/ws/metadata/v3/check-id-availability?id=attasidor) | Check if a given resource ID is available |
| 🔧 [/renew-cache](https://ws.spraakbanken.gu.se/ws/metadata/v3/renew-cache) | Update all metadata files from git, re-process JSON, and update cache. |
| 🔧 [/renew-cache?resource-paths=[resource-type]/[resource-id]](https://ws.spraakbanken.gu.se/ws/metadata/v3/renew-cache?resource-paths=corpus/attasidor) | Update cache for specific resources, e.g.:<br>`resource-paths=corpus/attasidor,lexicon/saldo` |
| 📘 [/redoc](https://ws.spraakbanken.gu.se/ws/metadata/v3/redoc) | View the API documentation. |
| 📘 [/docs/dev-docs/](https://ws.spraakbanken.gu.se/ws/metadata/v3/docs/dev-docs/) | View the developer documentation. |
| 📘 [/resource-schema](https://ws.spraakbanken.gu.se/ws/metadata/v3/resource-schema) | Return the JSON schema which is used to validate the metadata YAML files. |
| 📘 [/openapi.json](https://ws.spraakbanken.gu.se/ws/metadata/v3/openapi.json) | Serve API documentation as JSON |

## Requirements

- [Python 3.11](https://docs.python.org/3.11/) or newer
- [Redis](https://redis.io/) (used for Celery background tasks)
- [Memcached](https://memcached.org/) (for optional caching)

## Installation

To install the dependencies, we recommend using [uv](https://docs.astral.sh/uv/).

1. Install [uv](https://docs.astral.sh/uv/getting-started/installation/) if you don't have it already.
2. While in the metadata-api directory, run:

   ```sh
   uv sync --no-install-project
   ```

   This will create a virtual environment in the `.venv` directory and install the dependencies listed in
   `pyproject.toml`.

Alternatively, you can set up a virtual environment manually using Python's built-in `venv` module and install the
dependencies using pip:

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Configuration

The default configuration is specified in `metadata_api/settings.py`. You can override these settings using environment
variables or by creating a local `.env` file in the project's root directory. Common configuration options include:

- `LOG_LEVEL` (default: `INFO`)
- `LOG_TO_FILE` (default: `True`): Logs always go to stdout; if `True`, they are also saved to
  `logs/metadata_api_<DATE>.log`.
- `ROOT_PATH`: The root path for the API, e.g., "/metadata-api" if served from a subpath.
- `METADATA_DIR`: Absolute path to the directory containing the [metadata YAML
  files](https://github.com/spraakbanken/metadata).
- `CELERY_BROKER_URL`: URL for the Celery broker used for background tasks.
- `MEMCACHED_SERVER`: Host and port of the Memcached server, or path to the socket file.
- `SLACK_WEBHOOK`: URL to a Slack webhook for error notifications (optional).

Example `.env` file:

```env
LOG_LEVEL=DEBUG
LOG_TO_FILE=False
ROOT_PATH="/metadata-api"
METADATA_DIR="/path-to-metadata-dir"
CELERY_BROKER_URL="redis://localhost:6379/1"
MEMCACHED_SERVER="localhost:11211"  # Set to None to disable caching
SLACK_WEBHOOK="https://hooks.slack.com/services/..."
```

## Running a Test Server

For testing purposes, you can run the app using the following script (with an activated virtual environment, or by
prefixing with `uv run`). The default settings when using `run.py` are:

- Host/port: `127.0.0.1:8000`
- `ENV=development`
- `LOG_LEVEL=DEBUG`
- `LOG_TO_FILE=False` (logs to console only)
- `reload=True` (auto-restart on code changes)

```bash
python run.py [--host HOST] [--port PORT] [--log-level LOG_LEVEL]
```

If you prefer to run the app with `uvicorn`, you can use the following command:

```bash
uvicorn metadata_api.main:app
```

You also need to have a running Celery worker for background tasks. You can start a worker with:

```bash
celery -A metadata_api.tasks worker --loglevel=INFO
```

Please note that you need to have a running [Redis](https://redis.io/) server for Celery to work.

## Viewing the Developer Documentation

The application builds the MkDocs site at startup and serves the developer documentation, PID/DOI guide, and changelog
from `/docs/`. When running a local server, open <http://127.0.0.1:8000/docs/>.
