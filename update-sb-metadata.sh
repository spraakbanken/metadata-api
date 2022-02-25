#!/usr/bin/env bash

set +x

# Make logdir and define logfile
LOGDIR=/home/fksbwww/sb-metadata/logs
mkdir -p $LOGDIR
LOGFILE=$LOGDIR/`date +%Y-%m`.log

# Fetch updates in metadata files from SVN
echo -e "\n" >> $LOGFILE
date >> $LOGFILE
echo ">>> Update metadata from SVN" >> $LOGFILE
cd /home/fksbwww/sb-metadata/meta-share/corpus && svn update
cd /home/fksbwww/sb-metadata/meta-share/lexicon && svn update
cd /home/fksbwww/sb-metadata/meta-share/model && svn update
cd /home/fksbwww/sb-metadata/meta-share/resource-texts && svn update
cd /home/fksbwww/sb-metadata/json/corpus && svn update
cd /home/fksbwww/sb-metadata/json/lexicon && svn update
cd /home/fksbwww/sb-metadata/json/model && svn update

# Fetch application updates from GitHub and restart if necessary
cd /home/fksbwww/sb-metadata
git_output=`git pull`
echo -e ">>> Result of 'git pull': $git_output" >> $LOGFILE
if [[ "$git_output" != *"Already"* ]]; then
  echo ">>> Restart sb-metadata" >> $LOGFILE
  supervisorctl -c ~/fksbwww.conf restart metadata
  echo ">>> Done" >> $LOGFILE
fi

# Parse metadata files and flush cache
echo ">>> Parsing meta data" >> $LOGFILE
cd /home/fksbwww/sb-metadata
source venv/bin/activate
cd parse
python parse_metashare.py
deactivate
echo ">>> Flush cache" >> $LOGFILE
curl -s 'https://ws.spraakbanken.gu.se/ws/metadata/renew-cache' >> $LOGFILE


# Naive log rotation: delete files that are more than six months old
this_year=`date +%Y`
this_month=`date +%m`
FILES="$LOGDIR/*.log"
for f in $FILES
do
  filename="$(basename -- $f)"
  year="$(echo ${filename%.*} | cut -d'-' -f1)"
  month="$(echo ${filename%.*} | cut -d'-' -f2)"

  if [ "$(((this_year - year) * 12 - 10#$month + this_month))" -gt 6 ]
  then
    echo "Removing out-dated log file $filename" >> $LOGFILE
    rm "$f"
  fi
done
