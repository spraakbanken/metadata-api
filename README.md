# Språkbanken Text Metadata

This repository contains the following components:

- **/metadata-api** - a REST-API that serves metadata for SB's corpora, lexicons, models, analyses and utilities (mainly used by our site at spraakbanken.gu.se). For documentation see below.
- **/gen_pids/gen_pids.py** - a Python script that generates new PIDs (Datacite DOIs) by reading our metadata YAML-files and registering resources at Datacite. For documentation see the code comments and the /docs directory.
- **/metadata_api/parse_yaml.py** - a script that prepares data for the REST-API (might be deprecated due to integration in the API)
- **update_metadata.sh** - a shell script that runs periodically on the server and calls and starts the other components. It also handles all the git updating as both `gen_pids.py` and `parse_yaml.py` work with our [metadata](https://github.com/spraakbanken/metadata) repository.

## Requirements

- [Python 3](https://docs.python.org/3/)
- [Memcached](https://memcached.org/) (optional)

## Usage

Available API calls (please note that the URL contains the API version, e.g. `v3`, `dev` etc):

- <https://ws.spraakbanken.gu.se/ws/metadata/v3/>: List all resources
- <https://ws.spraakbanken.gu.se/ws/metadata/v3/corpora>: List all corpora
- <https://ws.spraakbanken.gu.se/ws/metadata/v3/lexicons>: List all lexicons
- <https://ws.spraakbanken.gu.se/ws/metadata/v3/models>: List all models
- <https://ws.spraakbanken.gu.se/ws/metadata/v3/analyses>: List all analyses
- <https://ws.spraakbanken.gu.se/ws/metadata/v3/utilities>: List all utilities
- <https://ws.spraakbanken.gu.se/ws/metadata/v3/collections>: List all collections
- <https://ws.spraakbanken.gu.se/ws/metadata/v3/?resource=saldo>: List one specific resource. Add long resource description (if available)
- <https://ws.spraakbanken.gu.se/ws/metadata/v3/schema>: Return JSON schema for resources
- <https://ws.spraakbanken.gu.se/ws/metadata/v3/list-ids>: List all existing resource IDs
- <https://ws.spraakbanken.gu.se/ws/metadata/v3/check-id-availability?id=[my-resource]>: Check if a given resource ID is free
- <https://ws.spraakbanken.gu.se/ws/metadata/v3/bibtex?resource=[some-id]>: Return bibtex citation for specified resource
- <https://ws.spraakbanken.gu.se/ws/metadata/v3/doc>: Serve API documentation as JSON
- <https://ws.spraakbanken.gu.se/ws/metadata/v3/renew-cache>: Update metadata files from git, re-process json files and update cache.
  optional parameters: `?debug=True` will print debug info, `?offline=True` will omit getting file info for downloadables when parsing YAML files,
  `?resource-paths=<resource_type/resource_id>,...` will process specific resources only.

## Installation (SBX-specific)

- Install requirements from `requirements.txt`, e.g. with a (virtual environment):

  ```.bash
  python3 -m venv venv
  source venv/bin/activate
  pip install -r requirements.txt
  ```

- The app can be configured by creating `config.py` in the root directory. The configuration in `config_default.py` is
  always loaded automatically but its values can be overridden by `config.py`.

- [Create a deploy
  key](https://docs.github.com/en/authentication/connecting-to-github-with-ssh/managing-deploy-keys#set-up-deploy-keys),
  add it to the [metadata repository](https://github.com/spraakbanken/metadata) and [edit your ssh
  configuration](https://docs.github.com/en/authentication/connecting-to-github-with-ssh/managing-deploy-keys#using-multiple-repositories-on-one-server).

- Clone the metadata repository with ssh and the host set in the ssh configuration:

  ```.bash
  git clone git@github.com-metadata:spraakbanken/metadata.git
  ```

- Add entry in supervisord config, e.g:

  ```.bash
  [program:metadata]
  command=%(ENV_HOME)s/metadata-api/dev/venv/bin/gunicorn --chdir %(ENV_HOME)s/metadata-api/dev -b "0.0.0.0:1337" metadata_api:create_app()
  ```

- Install [Memcached](https://memcached.org/) and setup. e.g. through supervisord:

  ```.bash
  [program:memcached-metadata]
  command=%(ENV_HOME)s/memcached-jox/memcached-install/bin/memcached
         -v
  ```

- When app is running, call the `/renew-cache` route in order to create the necessary JSON files and populate the cache.

- Store Datacite login credentials in `/home/fksbwww/.netrc` (check [pid_creation.md](docs/pid_creation.md) for more info).

- Set up cron job that periodically runs `gen_pids.sh` to add DOIs to resources. The following cron job is run on `fksbwww@k2`:

  ```.bash
  # Update Datacite metadata once per week
  15 23 * * 0 cd /home/fksbwww/metadata-api/v3 && ./gen_pids.sh > /dev/null
  ```

## Comments about some metadata fields

### Collections

A collection is a "meta" metadata entry which is used to summarize multiple resources. Collections are supplied as YAML
files. The resource-IDs belonging to a collection can either be supplied as a list in the YAML (with the 'resources'
key) or each resource can state which collection(s) it belongs to in its YAML (with the 'in_collections' key which holds
a list of collection IDs). The size of the collection is calculated automatically. A collection may have a resource
description in its YAML.

### Unlisted

Resources with the attribute `"unlisted": true` will not be listed in the data list on the web page, but they can be
accessed directly via their URL. This is used as a quick and dirty versioning system.

### Successors

The `successors` attribute can be used for resources that have been superseded by one or more other resources (e.g.
newer versions). This attribute holds a list of resource IDs.
