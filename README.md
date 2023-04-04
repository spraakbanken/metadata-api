# metadata-api

REST-API that serves meta data for SB's corpora, lexicons and models.

## Requirements

* [Python 3](https://docs.python.org/3/)
* [Memcached](https://memcached.org/) (optional)

## Usage

Available API calls:

- `https://ws.spraakbanken.gu.se/ws/metadata`: List all resources in three dictionaries (`corpora`, `lexicons`, and `models`)
- `https://ws.spraakbanken.gu.se/ws/corpora`: List all corpora
- `https://ws.spraakbanken.gu.se/ws/lexicons`: List all lexicons
- `https://ws.spraakbanken.gu.se/ws/models`: List all models
- `https://ws.spraakbanken.gu.se/ws/collections`: List all collections
- `https://ws.spraakbanken.gu.se/ws/metadata?resource=saldo`: List one specific resource. Add long description from SVN (if available)
- `https://ws.spraakbanken.gu.se/ws/metadata?has-description=true`: List only resources that have a long description
- `https://ws.spraakbanken.gu.se/ws/metadata/doc`: Serve API documentation as YAML
- `https://ws.spraakbanken.gu.se/ws/metadata/renew-cache`: Flush cache and fill with fresh values

## Installation (SBX-specific)

- Install requirements from `requirements.txt`, e.g. with a (virtual environment):
  ```
  python3 -m venv venv
  source venv/bin/activate
  pip install -r requirements.txt
  ```

- Get an initial copy of the metadata files (META-SHARE and YAML) and resource descriptions:
  ```
   ./get_metadata.sh
  ```

- Add entry in supervisord config:
  ```
  [program:metadata]
  command=%(ENV_HOME)s/metadata-api/venv/bin/gunicorn --chdir %(ENV_HOME)s/metadata-api -b "0.0.0.0:1337" metadata_api:create_app()
  ```

- Create the file `config.sh` in the root of this project and set the variables `SVN_USER` and `SVN_PWD` with the SVN credentials.

- Set up cron job that periodically runs the update script which 
  - updates the YAML files stored in git
  - updates the META-SHARE files and resource descriptions from SVN
  - runs the python script for parsing these files
  - updates the repository from GitHub and restarts the service if needed
  - creates missing META-SHARE files

  The following cron job is run on fksbwww@k2:
  ```
  # Update sb-metadata from SVN and GitHub and restart if needed
  50 * * * * cd /home/fksbwww/metadata-api && ./update_metadata.sh > /dev/null
  ```


## Resource texts (long resource descriptions)

Some resources have long descriptions that are stored in separate HTML files in SVN
(https://svn.spraakdata.gu.se/sb-arkiv/pub/resurstext). A description for a resource with machine name `my-resource`
should be named `my-resource_eng.html` or `my-resource_swe.html` and stored in the above SVN repository. Then it will
automatically be detected and served by the REST-API. A resource description can also be supplied directly in the YAML
metadata.


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
