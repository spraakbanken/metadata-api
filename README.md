This repo contains several components:
* **/metadata-api** - a REST-API that serves meta data for SB's corpora, lexicons and models (mainly used by our site at spraakbanken.gu.se). For documentation see below.
* **/parse/gen_pids.py** - a Python script that generates new PIDs (Datacite DOIs) by reading our metadata YAML-files and registering resources at Datacite. For documentation see below (after the metadata-api documentation).
* **/parse/parse_yaml.py** - a sript that prepares data for the REST-API
* **update_metadata.sh** - a shell script that runs periodically on the server and calls and starts the other components. It also handles all the git stuff as both gen_pids.py and parse_yaml.py works with our [metadata](https://github.com/spraakbanken/metadata) repository

# metadata-api

## Requirements

* [Python 3](https://docs.python.org/3/)
* [Memcached](https://memcached.org/) (optional)

## Usage

Available API calls:

- `https://ws.spraakbanken.gu.se/ws/metadata`: List all resources in three dictionaries (`corpora`, `lexicons`, and `models`)
- `https://ws.spraakbanken.gu.se/ws/metadata/corpora`: List all corpora
- `https://ws.spraakbanken.gu.se/ws/metadata/lexicons`: List all lexicons
- `https://ws.spraakbanken.gu.se/ws/metadata/models`: List all models
- `https://ws.spraakbanken.gu.se/ws/metadata/collections`: List all collections
- `https://ws.spraakbanken.gu.se/ws/metadata?resource=saldo`: List one specific resource. Add long description from SVN (if available)
- `https://ws.spraakbanken.gu.se/ws/metadata/list_ids`: List all existing resource IDs
- `https://ws.spraakbanken.gu.se/ws/metadata/check-id-availability?id=my-resource`: Check if a given resource ID is free
- `https://ws.spraakbanken.gu.se/ws/metadata/doc`: Serve API documentation as YAML
- `https://ws.spraakbanken.gu.se/ws/metadata/renew-cache`: Flush cache and fill with fresh values

## Installation (SBX-specific)

- Install requirements from `requirements.txt`, e.g. with a (virtual environment):
  ```
  python3 -m venv venv
  source venv/bin/activate
  pip install -r requirements.txt
  ```

- Get an initial copy of the metadata files:
  ```
   git clone https://github.com/spraakbanken/metadata.git
  ```

- Add entry in supervisord config:
  ```
  [program:metadata]
  command=%(ENV_HOME)s/metadata-api/venv/bin/gunicorn --chdir %(ENV_HOME)s/metadata-api -b "0.0.0.0:1337" metadata_api:create_app()
  ```

- Set up cron job that periodically runs the update script which 
  - updates the metadata files stored in git
  - runs the python script for parsing these files
  - updates the repository from GitHub and restarts the service if needed

  The following cron job is run on fksbwww@k2:
  ```
  # Update sb-metadata from GitHub and restart if needed
  50 * * * * cd /home/fksbwww/metadata-api && ./update_metadata.sh > /dev/null
  ```


## Collections

A collection is a "meta" metadata entry which is used to summarize multiple resources. Collections are supplied as YAML
files. The resource-IDs belonging to a collection can either be supplied as a list in the YAML (with the 'resources'
key) or each resource can state which collection(s) it belongs to in its YAML (with the 'in_collections' key which holds
a list of collection IDs). The size of the collection is calculated automatically. A collection may have a resource
description in its YAML.


## Unlisted

Resources with the attribute `"unlisted": true` will not be listed in the data list on the web page, but they can be 
accessed directly via their URL. This is used as a quick and dirty versioning system.


## Successors

The `successors` attribute can be used for resources that have been superseded by one or more other resources (e.g.
newer versions). This attribute holds a list of resource IDs.

# gen_pids.py

For documentation see the code comments and the /docs directory.

## Storing credentials
The Datacite login credentials are store in a .netrc file located in /home/fksbwww on the server.
