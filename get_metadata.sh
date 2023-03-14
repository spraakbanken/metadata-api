#!/usr/bin/env bash

# Script for retrieving meta data from SVN (META-SHARE) and git (YAML)

mkdir -p meta-share/corpus
mkdir -p meta-share/lexicon
mkdir -p meta-share/model

svn co https://svn.spraakdata.gu.se/sb-arkiv/pub/metadata/corpus meta-share/corpus/
svn co https://svn.spraakdata.gu.se/sb-arkiv/pub/metadata/lexicon meta-share/lexicon/
svn co https://svn.spraakdata.gu.se/sb-arkiv/pub/metadata/model meta-share/model/

mkdir -p yaml
git clone https://github.com/spraakbanken/metadata.git yaml
