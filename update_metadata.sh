#!/usr/bin/env bash

set +x
export LANG=en_US.UTF-8
THISDIR=$PWD

# Make logdir and define logfile
LOGDIR=$THISDIR/logs
mkdir -p $LOGDIR
LOGFILE=$LOGDIR/`date +%Y-%m`.log

############################################
# UPDATE APPLICATION
############################################
# Fetch application updates from GitHub and restart if necessary
cd $THISDIR
git_output2=`git pull 2>&1`
echo -e ">>> Result of 'git pull': $git_output2" >> $LOGFILE
if [[ "$git_output2" != *"Already"* ]]; then
  echo ">>> Update venv" >> $LOGFILE
  source venv/bin/activate
  pip install -r requirements.txt
  echo ">>> Restart sb-metadata" >> $LOGFILE
  supervisorctl -c ~/fksbwww.conf restart metadata
  echo ">>> Done" >> $LOGFILE
fi

############################################
# UPDATE METADATA
############################################
# Fetch updates in metadata files
echo -e "\n" >> $LOGFILE
date >> $LOGFILE
echo ">>> Update metadata from GIT" >> $LOGFILE
cd $THISDIR/metadata
git_output1=`git pull 2>&1`
# Send output to stderr if git command had a non-zero exit
if [[ $? -ne 0 ]] ; then
    >&2 echo $git_output1
else
    echo "$git_output1" >> $LOGFILE
fi

# Flush cache (results in re-parsing all metadata files)
# TODO: Do this with a webhook instead and only update cache for changed files
echo ">>> Flush cache" >> $LOGFILE
curl -s 'https://ws.spraakbanken.gu.se/ws/metadata/renew-cache' >> $LOGFILE

############################################
# DATACITE
############################################
# Parse metadata files and generate PIDs
cd $THISDIR
source venv/bin/activate
echo ">>> Parsing metadata - generate PIDs" >> $LOGFILE
cd $THISDIR/gen_pids
python gen_pids.py $1 >> $LOGFILE
cd $THISDIR/metadata/yaml
git_output3=$(git add --all . 2>&1)
if [[ $? -ne 0 ]]; then
    >&2 echo $git_output3
fi
# Commit and push all changes
git_output4=$(git diff-index --quiet HEAD || git -c user.name='sb-sparv' -c user.email='38045079+sb-sparv@users.noreply.github.com' commit -m "added PIDs through cron" 2>&1)
if [[ $? -ne 0 ]]; then
    >&2 echo $git_output4
fi
git_output5=$(git push 2>&1)
if [[ $? -ne 0 ]]; then
    >&2 echo $git_output5
fi

############################################
# LOG ROTATION
############################################
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
