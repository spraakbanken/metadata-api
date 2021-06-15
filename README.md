# sb-metadata
REST-API that serves meta data for SB's corpora, lexicons and models

## Requirements

* [Python 3](https://docs.python.org/3/)
* [Memcached](https://memcached.org/) (optional)

## Usage

Available API calls:

- `https://ws.spraakbanken.gu.se/ws/metadata`: List all resources in three dictionaries (`corpora`, `lexicons`, and `models`)
- `https://ws.spraakbanken.gu.se/ws/metadata?resource=saldo`: List one specific resource. Add long description from SVN (if available)
- `https://ws.spraakbanken.gu.se/ws/metadata?has-description=true`: List only resources that have a long description
- `https://ws.spraakbanken.gu.se/ws/metadata/doc`: Serve API documentation as YAML
- `https://ws.spraakbanken.gu.se/ws/metadata/renew-cache`: Flush cache and fill with fresh values

## Installation (SB-specific)

- Install requirements from `requirements.txt`, e.g. with a (virtual environment):
  ```
  python3 -m venv venv
  source venv/bin/activate
  pip install -r requirements.txt
  ```

- Get an initial copy of the META-SHARE files and resource descriptions:
  ```
   ./get_metadata.sh
  ```

- Add entry in supervisord config:
  ```
  [program:metadata]
  command=%(ENV_HOME)s/sb-metadata/venv/bin/gunicorn --chdir %(ENV_HOME)s/sb-metadata -b "0.0.0.0:1337" metadata:create_app()
  ```

- Set up cron job that periodically runs the update script which 
  - updates the META-SHARE files and resource descriptions from SVN
  - runs the python script for parsing these files
  - updates the repository from GitHub and restarts the service if needed

  The following cron job is run on fksbwww@k2:
  ```
  # Update sb-metadata from SVN and GitHub and restart if needed
  50 * * * * cd /home/fksbwww/sb-metadata && ./update-sb-metadata.sh > /dev/null
  ```


## Resource texts (long resource descriptions)

Some resources have long descriptions that cannot be stored in the META-SHARE xml files.
These descriptions are stored as html files in SVN (https://svn.spraakdata.gu.se/sb-arkiv/pub/resurstext).
A description for a resource with machine name `my-resource` should be named `my-resource_eng.html` or `my-resource_swe.html`
and stored in the above SVN repository. In this case it will automatically be detected and served by the REST-API.


## Blacklisted resources

Some resources need to have META-SHARE files for technical reasons (e.g. because they are neede in the wsauth system), but we may not want to show them publicly in the API. For this purpose one can add resource IDs to the lists in `parse/blacklist.py`.
