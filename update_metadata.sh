#!/usr/bin/env bash

set +x
THISDIR=$PWD

# Make logdir and define logfile
LOGDIR=$THISDIR/logs
mkdir -p $LOGDIR
LOGFILE=$LOGDIR/`date +%Y-%m`.log

# Fetch updates in metadata files from SVN
echo -e "\n" >> $LOGFILE
date >> $LOGFILE
echo ">>> Update metadata from GIT" >> $LOGFILE
cd $THISDIR/json && git pull
echo ">>> Update metadata from SVN" >> $LOGFILE
cd $THISDIR/meta-share/corpus && svn update
cd $THISDIR/meta-share/lexicon && svn update
cd $THISDIR/meta-share/model && svn update
cd $THISDIR/meta-share/resource-texts && svn update

# Fetch application updates from GitHub and restart if necessary
cd $THISDIR
git_output=`git pull`
echo -e ">>> Result of 'git pull': $git_output" >> $LOGFILE
if [[ "$git_output" != *"Already"* ]]; then
  echo ">>> Restart sb-metadata" >> $LOGFILE
  supervisorctl -c ~/fksbwww.conf restart metadata
  echo ">>> Done" >> $LOGFILE
fi

# Parse metadata files and flush cache
echo ">>> Parsing meta data" >> $LOGFILE
cd $THISDIR
source venv/bin/activate
cd parse
python parse_json.py
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

  # Convert month ints to base 10 to avoid errors when `08` and `09` are parsed as octal
  if [ "$(((this_year - year) * 12 + 10#$this_month - 10#$month))" -gt 6 ]
  then
    echo "Removing out-dated log file $filename" >> $LOGFILE
    rm "$f"
  fi
done
