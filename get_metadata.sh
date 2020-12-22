#!/usr/bin/env bash

# Script for retrieving meta data from SVN (META-SHARE + JSON) and long resource descriptions

mkdir -p meta-share/corpus
mkdir -p meta-share/lexicon
mkdir -p meta-share/model
mkdir -p meta-share/resource-texts
mkdir -p json/corpus
mkdir -p json/lexicon
mkdir -p json/model

svn co https://svn.spraakdata.gu.se/sb-arkiv/pub/metadata/corpus meta-share/corpus/
svn co https://svn.spraakdata.gu.se/sb-arkiv/pub/metadata/lexicon meta-share/lexicon/
svn co https://svn.spraakdata.gu.se/sb-arkiv/pub/metadata/model meta-share/model/
svn co https://svn.spraakdata.gu.se/sb-arkiv/pub/resurstext meta-share/resource-texts/
svn co https://svn.spraakdata.gu.se/sb-arkiv/pub/metadata/metadata-json/corpus/ json/corpus/
svn co https://svn.spraakdata.gu.se/sb-arkiv/pub/metadata/metadata-json/lexicon/ json/lexicon/
svn co https://svn.spraakdata.gu.se/sb-arkiv/pub/metadata/metadata-json/model/ json/model/
