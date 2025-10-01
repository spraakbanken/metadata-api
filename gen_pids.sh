#!/usr/bin/env bash

set +x
export LANG=en_US.UTF-8
THISDIR=$PWD

# Make logdir and define logfile
LOGDIR=$THISDIR/logs
mkdir -p $LOGDIR
LOGFILE=$LOGDIR/`date +%Y-%m`.log

############################################
# DATACITE
############################################
# Parse metadata files and generate PIDs
cd $THISDIR
source venv/bin/activate
echo ">>> Parsing metadata - generate PIDs" >> $LOGFILE
cd $THISDIR/gen_pids
python gen_pids.py $0 >> $LOGFILE
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
FILES=$(find $LOGDIR -type f -name '[0-9][0-9][0-9][0-9]-[0-9][0-9].log')
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
