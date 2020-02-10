This directory contains scripts that are used to create and update metadata files for Språkbanken's corpora.
The scripts are used on `bark:/home/fksparv/sb-metadata/update-meta-share`

### `update-corpus-statistics.py`

Updates a metadata file with the amount of sentences and tokens in the corpus.

Usage:
`python3 update-corpus-statistics.py METADATAFILE.xml`


### `create_metadata.py:`

Creates META-SHARE xml files for corpora by copying a template xml and adapting the contents given by a config file.

The directories `configs` and `templates` contain example files.

For more info run:
`python create_metadata.py -h`


### Cron job for updating all corpus sizes

The following cron job is run on bark:

`5 0 * * * cd /home/fksparv/sb-metadata/update-meta-share/ && source venv/bin/activate && python3 update-corpus-stats.py $(ls /home/fksparv/sb-metadata/meta-share/corpus/*.xml | tr '\n' ' ') && svn ci -m "cron update"`
