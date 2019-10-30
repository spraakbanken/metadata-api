# sb-metadata
REST-API that serves meta data for SB's corpora and lexicons

## Requirements

* [Python 3](https://docs.python.org/3/)

## Installation

- Install requirements from `requirements.txt`, e.g. with a (virtual environment):

  python3 -m venv venv
  source venv/bin/activate
  pip install -r requirements.txt


- Set up cron job that periodically updates the meta share files from SVN and re-parses them
