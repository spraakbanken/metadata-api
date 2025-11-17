# Developer documentation

## Project structure

This project contains the following main components:

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

## Bumping the version number

When increasing the version number of the app, update the `__version__` variable in
[`__init__.py`](metadata_api/__init__.py). If you change the major version, run [`set_version.sh`](set_version.sh) to
automatically update all version references in this README file.

## Caching

Caching can be used in the API to improve response times. [Memcached](https://memcached.org/) is used for this purpose
and can be configured in `config.py` with the following settings:

```python
# Caching settings
NO_CACHE = False  # Set to True to disable caching with memcached
MEMCACHED_HOST = "localhost"
MEMCACHED_PORT = 11211
```

### What is being cached?

- All data for each resource type as a dictionary (example key: `corpus.json`)
- Data for each resource as a dictionary (example key: `attasidor`)
- Resource descriptions for each resource that has one (example key: `res_descr_attasidor`)

### Cache renewal

Cache renewal can be triggered by calling the `/renew-cache` route. This will do the following:

- Changes from the [metadata repository](https://github.com/spraakbanken/metadata) will be pulled from GitHub to update
  the metadata YAML files.
- Metadata YAML files will be reprocessed (either all of them or just the ones specified by the `resource-paths`
  parameter, or the files that were changed in the last push event, specified by the GitHub webhook call) and the static
  JSON files used by the API will be regenerated.
- If memcached caching is activated, the cache is flushed and repopulated with data from the updated JSON files.

## Deployment (SBX-specific)

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
