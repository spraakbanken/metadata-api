# Developer documentation

## Project structure

This project contains the following main components:

- [**`metadata_api`**](/metadata_api/) - A REST API that serves [metadata](https://github.com/spraakbanken/metadata) for
  Språkbanken Text's corpora, lexicons, models, analyses, and utilities (mainly used by our site at spraakbanken.gu.se).
  For documentation, see below.
- [**`parse_yaml.py`**](/metadata_api/parse_yaml.py) - A script that prepares data for the REST API. This component is
  called automatically upon [cache renewal](#cache-renewal) but can also be run as a script locally (although this
  functionality is deprecated).
- [**`tasks.py`**](/metadata_api/tasks.py) - Celery background tasks for the REST API, e.g. for cache renewal.
- [**`gen_pids.py`**](/gen_pids/gen_pids.py) - A Python script that generates new PIDs (Datacite DOIs) by reading our
  metadata YAML files and registering resources at Datacite. For documentation, see the code comments and
  [`pid_creation.md`](/docs/pid_creation.md).
- [**`gen_pids.sh`**](gen_pids.sh) - A shell script that runs periodically on the server (via cron) and calls
  [`gen_pids.py`](/gen_pids/gen_pids.py).

## Bumping the version number

If you want to bump the app version number, update the `version` field in [`pyproject.toml`](pyproject.toml). If you
change the major version, run [`set_version.sh`](set_version.sh) to automatically update all version references in the
URLs in the [README file](README.md).

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

Cache renewal can be triggered by calling the `/renew-cache` route. This will trigger a background task with celery that
will do the following:

- Changes from the [metadata repository](https://github.com/spraakbanken/metadata) will be pulled from GitHub to update
  the metadata YAML files.
- Metadata YAML files will be reprocessed (either all of them or just the ones specified by the `resource-paths`
  parameter, or the files that were changed in the last push event, specified by the GitHub webhook call) and the static
  JSON files used by the API will be regenerated.
- If memcached caching is activated, the cache is flushed and repopulated with data from the updated JSON files.

The `/renew-cache` route can be called manually (e.g. via curl) but it is usually also set up as a webhook in the
metadata repository to be triggered automatically upon each push event to the main branch.

The response from the `/renew-cache` route will **not** contain the results of the cache renewal itself, since this is
done in the background. If `SLACK_WEBHOOK_URL` is set in the configuration and any errors or warnings occur, a message
with the results of the cache renewal will be sent to the specified Slack channel when the task is finished. Messages
from the task will also be logged to the celery worker log.

## Deployment (SBX-specific)

Set up the metadata-api app by following the [installation instructions](../README.md#installation) in the README file
to install the dependencies. Don't forget to add your own configuration to the app as described under
[Configuration](../README.md#configuration).

### Setting up the metadata repository

- [Create a deploy
  key](https://docs.github.com/en/authentication/connecting-to-github-with-ssh/managing-deploy-keys#set-up-deploy-keys),
  add it to the [metadata repository](https://github.com/spraakbanken/metadata) and [edit your ssh
  configuration](https://docs.github.com/en/authentication/connecting-to-github-with-ssh/managing-deploy-keys#using-multiple-repositories-on-one-server).

- Clone the metadata repository with ssh and the host set in the ssh configuration:

  ```bash
  git clone git@github.com-metadata:spraakbanken/metadata.git
  ```

### Setting up the services

- Install [Redis](https://redis.io/) (used as broker for Celery background tasks) and
  [Memcached](https://memcached.org/) (for optional caching).

- Create a directory where Redis can store data and add it to the Redis configuration file, e.g.:

  ```bash
  mkdir /home/fksbwww/redisdata
  echo "dir /home/fksbwww/redisdata" >> /home/fksbwww/redis-install/redis.conf
  ```

- Add entries in supervisord config for the metadata-api, the celery worker, redis and memcached, e.g:

  ```bash
  [program:metadata]
  command=%(ENV_HOME)s/metadata-api/dev/venv/bin/gunicorn --chdir %(ENV_HOME)s/metadata-api/dev -b "0.0.0.0:1337" --worker-class gevent --workers 4 metadata_api:create_app()

  [program:metadata-celery]
  command=%(ENV_HOME)s/metadata-api/dev/venv/bin/celery -A metadata_api.tasks worker --loglevel=INFO
  directory=%(ENV_HOME)s/metadata-api/dev/

  [program:redis-metadata]
  command=%(ENV_HOME)s/redis-install/src/redis-server %(ENV_HOME)s/redis-install/redis.conf

  [program:memcached-metadata]
  command=%(ENV_HOME)s/memcached-jox/memcached-install/bin/memcached
         -v
  ```

- Update supervisord and start the services with `supervisorctl update`.

### Final setup steps

- When the app is up and running, call the `/renew-cache` route in order to create the necessary JSON files and populate
  the cache.

- Store Datacite login credentials in `/home/fksbwww/.netrc` (check [pid_creation.md](docs/pid_creation.md) for more
  info).

- Set up cron jobs that periodically run `gen_pids.sh` to add DOIs to resources and update Datacite. The following cron
  jobs are run on `fksbwww@k2`:

  ```bash
  # Generate pids every night
  5 1 * * * cd /home/fksbwww/metadata-api/v3 && ./gen_pids.sh --analyses --noupdate > /dev/null
  # Update Datacite metadata once per week
  15 23 * * 0 cd /home/fksbwww/metadata-api/v3 && ./gen_pids.sh > /dev/null
  ```
