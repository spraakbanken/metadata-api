# sb-metadata
REST-API that serves meta data for SB's corpora and lexicons

## Requirements

* [Python 3](https://docs.python.org/3/)

## Usage

Available API calls:

- `https://ws.spraakbanken.gu.se/ws/metadata`: List all resources in two dictionaries (`corpora` and `lexicons`)
- `https://ws.spraakbanken.gu.se/ws/metadata?resource=saldo`: List one specific resource. Add long description from SVN (if available)
- `https://ws.spraakbanken.gu.se/ws/metadata?has-description=true`: List only resources that have a long description
- `https://ws.spraakbanken.gu.se/ws/metadata/doc`: Serve API documentation as YAML

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

- Set up cron job that periodically updates the META-SHARE files and resource descriptions from SVN.
  Also run python script for parsing these files.
  ```
  # Fetch meta share from SVN
  0 * * * * cd /home/fksparv/sb-metadata/meta-share/corpus && svn update > /dev/null
  0 * * * * cd /home/fksparv/sb-metadata/meta-share/lexicon && svn update > /dev/null
  0 * * * * cd /home/fksparv/sb-metadata/meta-share/resource-texts && svn update > /dev/null

  # Parse meta share to json
  5 * * * * cd /home/fksparv/sb-metadata && source venv/bin/activate && python parse_metashare.py
  ```

## Additional information

Some resources have long descriptions that cannot be stored in the META-SHARE xml files.
These descriptions are stored as html files in SVN (https://svn.spraakdata.gu.se/sb-arkiv/pub/resurstext).
A description for a resource with machine name `my-resource` should be named `my-resource_eng.html` or `my-resource_swe.html`
and stored in the above SVN repository. In this case it will automatically be detected and served by the REST-API.

If the naming convention cannot be met for some reason or if the description needs to be split in multiple files,
a new entry must be added in `resource_text_mapping.py` before the description is served by the API.

Please note that the mapping given in `resource_text_mapping.py` has precedence over existing files following the naming convention
(i.e. if there is an entry `my-resource` in `resource_text_mapping.py` then the description `my-resource_eng.html` will not be considered).
