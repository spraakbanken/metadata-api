#!/usr/bin/env bash
set -e

SB_METADATA_PATH="/home/fksparv/sb-metadata"

# Update repository
cd $SB_METADATA_PATH/meta-share/corpus
svn update

# Update corpus sizes in META-SHARE
cd $SB_METADATA_PATH/update-meta-share/
source venv/bin/activate
python3 update-corpus-stats.py $(ls $SB_METADATA_PATH/meta-share/corpus/*.xml | tr '\n' ' ')

# Check in changes
cd $SB_METADATA_PATH/meta-share/corpus
svn ci -m "cron update"
