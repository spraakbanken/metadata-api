#!/usr/bin/env bash

set +x

mkdir -p /home/fksparv/sb-metadata/logs

# Set SVN_USER, SVN_PWD and LOGFILE
source config.sh

echo -e "\n" >> $LOGFILE
date >> $LOGFILE
echo ">>> Update metadata from SVN" >> $LOGFILE
cd /home/fksparv/sb-metadata/meta-share/corpus && svn update && svn add * && svn ci -m "cron update" --username $SVN_USER --password $SVN_PWD
cd /home/fksparv/sb-metadata/meta-share/lexicon && svn update #&& svn add * && svn ci -m "cron update" --username $SVN_USER --password $SVN_PWD
cd /home/fksparv/sb-metadata/meta-share/model && svn update #&& svn add * && svn ci -m "cron update" --username $SVN_USER --password $SVN_PWD
cd /home/fksparv/sb-metadata/meta-share/resource-texts && svn update
cd /home/fksparv/sb-metadata/json/corpus && svn update && svn add * && svn ci -m "cron update" --username $SVN_USER --password $SVN_PWD
cd /home/fksparv/sb-metadata/json/lexicon && svn update #&& svn add * && svn ci -m "cron update" --username $SVN_USER --password $SVN_PWD
cd /home/fksparv/sb-metadata/json/model && svn update #&& svn add * && svn ci -m "cron update" --username $SVN_USER --password $SVN_PWD

cd /home/fksparv/sb-metadata
git_output=`git pull`
echo -e ">>> Result of 'git pull': $git_output" >> $LOGFILE
if [[ "$git_output" != *"Already"* ]]; then
  echo ">>> Restart sb-metadata" >> $LOGFILE
  supervisorctl -c ~/fksparv.conf restart metadata
  echo ">>> Done" >> $LOGFILE
fi

echo ">>> Parsing meta data" >> $LOGFILE
cd /home/fksparv/sb-metadata
source venv/bin/activate
cd parse
python parse_metashare.py >> $LOGFILE
deactivate
echo ">>> Flush cache" >> $LOGFILE
curl -s 'https://ws.spraakbanken.gu.se/ws/metadata/renew-cache' >> $LOGFILE
