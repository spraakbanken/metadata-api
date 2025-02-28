# Språkbanken Text Metadata API

This repository contains the following components:

- [**`metadata_api`**](/metadata_api/) - A REST API that serves [metadata](https://github.com/spraakbanken/metadata) for
  Språkbanken Text's corpora, lexicons, models, analyses, and utilities (mainly used by our site at spraakbanken.gu.se).
  For documentation, see below.
- [**`parse_yaml.py`**](/metadata_api/parse_yaml.py) - A script that prepares data for the REST API. This component is
  called automatically upon [cache renewal](/docs/caching.md) but can also be run as a script locally (although this
  functionality might be deprecated in the future).
- [**`gen_pids.py`**](/gen_pids/gen_pids.py) - A Python script that generates new PIDs (Datacite DOIs) by reading our
  metadata YAML files and registering resources at Datacite. For documentation, see the code comments and
  [`pid_creation.md`](/docs/pid_creation.md).
- [**`gen_pids.sh`**](gen_pids.sh) - A shell script that runs periodically on the server (via cron) and calls
  [`gen_pids.py`](/gen_pids/gen_pids.py).

## Requirements

- [Python 3](https://docs.python.org/3/)
- [Memcached](https://memcached.org/) (optional, check [caching.md](docs/caching.md) for more info)

## Usage

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
- <https://ws.spraakbanken.gu.se/ws/metadata/v3/schema>: Return JSON schema for resources
- <https://ws.spraakbanken.gu.se/ws/metadata/v3/list-ids>: List all existing resource IDs
- <https://ws.spraakbanken.gu.se/ws/metadata/v3/check-id-availability?id=[my-resource]>: Check if a given resource ID is
  free
- <https://ws.spraakbanken.gu.se/ws/metadata/v3/bibtex?resource=[some-id]>: Return bibtex citation for specified
  resource
- <https://ws.spraakbanken.gu.se/ws/metadata/v3/doc>: Serve API documentation as JSON
- <https://ws.spraakbanken.gu.se/ws/metadata/v3/renew-cache>: Update metadata files from git, re-process json files and
  update cache. optional parameters: `?debug=True` will print debug info, `?offline=True` will omit getting file info
  for downloadables when parsing YAML files, `?resource-paths=<resource_type/resource_id>,...` will process specific
  resources only.

## Installation (SBX-specific)

- Install requirements from `requirements.txt`, e.g. with a (virtual environment):

  ```bash
  python3 -m venv venv
  source venv/bin/activate
  pip install -r requirements.txt
  ```

- The app can be configured by creating `config.py` in the root directory. The configuration in
  [`config_default.py`](config_default.py) is always loaded automatically but its values can be overridden by
  `config.py`.

- [Create a deploy
  key](https://docs.github.com/en/authentication/connecting-to-github-with-ssh/managing-deploy-keys#set-up-deploy-keys),
  add it to the [metadata repository](https://github.com/spraakbanken/metadata) and [edit your ssh
  configuration](https://docs.github.com/en/authentication/connecting-to-github-with-ssh/managing-deploy-keys#using-multiple-repositories-on-one-server).

- Clone the metadata repository with ssh and the host set in the ssh configuration:

  ```bash
  git clone git@github.com-metadata:spraakbanken/metadata.git
  ```

- Add entry in supervisord config, e.g:

  ```bash
  [program:metadata]
  command=%(ENV_HOME)s/metadata-api/dev/venv/bin/gunicorn --chdir %(ENV_HOME)s/metadata-api/dev -b "0.0.0.0:1337" metadata_api:create_app()
  ```

- Install [Memcached](https://memcached.org/) and setup. e.g. through supervisord:

  ```bash
  [program:memcached-metadata]
  command=%(ENV_HOME)s/memcached-jox/memcached-install/bin/memcached
         -v
  ```

- When app is running, call the `/renew-cache` route in order to create the necessary JSON files and populate the cache.

- Store Datacite login credentials in `/home/fksbwww/.netrc` (check [pid_creation.md](docs/pid_creation.md) for more
  info).

- Set up cron jobs that periodically run `gen_pids.sh` to add DOIs to resources and update Datacite. The following cron
  jobs are run on `fksbwww@k2`:

  ```bash
  # Generate pids every night
  5 1 * * * cd /home/fksbwww/metadata-api/v3 && ./gen_pids.sh --noupdate > /dev/null
  # Update Datacite metadata once per week
  15 23 * * 0 cd /home/fksbwww/metadata-api/v3 && ./gen_pids.sh > /dev/null
  ```

## Running a test server

For testing purposes the app can be run with the following script (with an activated venv):

```bash
python run.py [--port PORT]
```

## Upgrading to a new app version

When increasing the version number of the app, update the `__version__` variable in
[`__init__.py`](metadata_api/__init__.py). If you change the major version, run [`set_version.sh`](set_version.sh) to
automatically update all version references in this README file.
