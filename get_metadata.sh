#!/usr/bin/env bash

# Script for retrieving meta data from SVN (META-SHARE) and long resource descriptions

mkdir -p meta-share/corpus
mkdir -p meta-share/lexicon
mkdir -p meta-share/resource-texts

svn co https://svn.spraakdata.gu.se/sb-arkiv/pub/metadata/corpus meta-share/corpus/
svn co https://svn.spraakdata.gu.se/sb-arkiv/pub/metadata/lexicon meta-share/lexicon/
svn co https://svn.spraakdata.gu.se/sb-arkiv/pub/resurstext meta-share/resource-texts/
