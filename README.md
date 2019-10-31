# sb-metadata
REST-API that serves meta data for SB's corpora and lexicons

## Requirements

* [Python 3](https://docs.python.org/3/)

## Installation (SB-specific)

- Install requirements from `requirements.txt`, e.g. with a (virtual environment):
  ```
  python3 -m venv venv
  source venv/bin/activate
  pip install -r requirements.txt
  ```

- Add entry in supervisord config:
  ```
  [program:metadata]
  command=%(ENV_HOME)s/sb-metadata/venv/bin/gunicorn --chdir %(ENV_HOME)s/sb-metadata -b "0.0.0.0:1337" metadata:create_app()
  ```

- Set up cron job that periodically updates the meta share files from SVN and re-parses them
  ```
  # Fetch meta share from SVN
  0 * * * * cd /home/fksparv/sb-metadata/meta-share/corpus && svn update > /dev/null
  0 * * * * cd /home/fksparv/sb-metadata/meta-share/lexicon && svn update > /dev/null

  # Parse meta share to json
  5 * * * * cd /home/fksparv/sb-metadata && source venv/bin/activate && python parse_metashare.py
  ```
