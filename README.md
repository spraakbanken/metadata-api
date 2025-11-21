# Språkbanken Text Metadata API

The Språkbanken Text Metadata API is a RESTful web service that provides access to metadata for various resources
maintained by Språkbanken Text, including corpora, lexicons, models, analyses, and utilities. The metadata is stored in
YAML files in a separate [metadata repository](https://github.com/spraakbanken/metadata).

For more technical details please refer to the [developer documentation](docs/dev-docs.md).

## API Usage

Available API calls (please note that the URL contains the API version, e.g. `/v3`, `/dev` etc):

- <https://ws.spraakbanken.gu.se/ws/metadata/v3/>: List all resources
- <https://ws.spraakbanken.gu.se/ws/metadata/v3/corpora>: List all corpora
- <https://ws.spraakbanken.gu.se/ws/metadata/v3/lexicons>: List all lexicons
- <https://ws.spraakbanken.gu.se/ws/metadata/v3/models>: List all models
- <https://ws.spraakbanken.gu.se/ws/metadata/v3/analyses>: List all analyses
- <https://ws.spraakbanken.gu.se/ws/metadata/v3/utilities>: List all utilities
- <https://ws.spraakbanken.gu.se/ws/metadata/v3/collections>: List all collections
- <https://ws.spraakbanken.gu.se/ws/metadata/v3/?resource=saldo>: List one specific resource. Add resource description
  (if available)
- <https://ws.spraakbanken.gu.se/ws/metadata/v3/renew-cache>: Update metadata files from git, re-process json files and
  update cache. optional parameters: `?debug=True` will print debug info, `?offline=True` will omit getting file info
  for downloadables when parsing YAML files, `?resource-paths=<resource_type/resource_id>,...` will process specific
  resources only.
- <https://ws.spraakbanken.gu.se/ws/metadata/v3/schema>: Return JSON schema for resources
- <https://ws.spraakbanken.gu.se/ws/metadata/v3/list-ids>: List all existing resource IDs
- <https://ws.spraakbanken.gu.se/ws/metadata/v3/check-id-availability?id=[my-resource]>: Check if a given resource ID is
  free
- <https://ws.spraakbanken.gu.se/ws/metadata/v3/bibtex?resource=[some-id]>: Return bibtex citation for specified
  resource
- <https://ws.spraakbanken.gu.se/ws/metadata/v3/doc>: Serve API documentation as JSON

## Requirements

- [Python 3.10](https://docs.python.org/3.10/) or newer
- [Redis](https://redis.io/) (used for Celery background tasks)
- [Memcached](https://memcached.org/) (for optional caching, check [caching.md](docs/caching.md) for more info)

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

The app can be configured by creating `config.py` in the root directory. The configuration in
[`config_default.py`](config_default.py) is always loaded automatically but its values can be overridden by `config.py`.

## Running a test server

For testing purposes the app can be run with the following script (with an activated venv):

```bash
python run.py [--port PORT]
```
