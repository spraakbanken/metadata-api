# -*- coding: UTF8 -*-

"""
Script for automatic creation of korp meta data files.
Usage: python create_metadata.py -c configfile -t templatefile
Takes a list of corpus specifications (configfile) and creates a new
meta data file similar to its template. Will adapt:
- resourceName (swe and eng)
- description (swe and eng)
- resourceShortName (swe and eng)
- identifier (name of meta data file)
- downloadLocation (meningsmängder) (if installed on k2)
- downloadLocation (statistics)
- executionLocation (link to korp)
- samplesLocation (location of meta data file)
- metadataCreationDate
- sizeInfo (tokens and sentences)

Make sure to have the correct iprHolder and metadataCreator in your templatefile,
as well as all the required xml-tags.
"""

import sys
import getopt
import time
import os
import codecs
import subprocess
from xml.etree import ElementTree as etree

# Where to store the created meta-share files (relative from where this script is run)
OUTPATH = "../meta-share/corpus/"

def main(argv):
    """Wrapper"""
    opts, args = getopt.getopt(argv, "c:t:h")
    configfile = templatexml = None

    helpmsg = """\nUsage: python create_metadata.py -c configfile -t templatefile
\nMake sure to have the correct iprHolder and metadataCreator in your templatefile, as well as all the required xml-tags. Run python create_metadata.py -h for more info.\n"""

    helpmsg_long = """\nUsage: python create_metadata.py -c configfile -t templatefile

Script for automatic creation of korp meta data files.
Takes a list of corpus specifications (configfile) and creates a new
meta data file similar to its template. Will adapt:
- resourceName (swe and eng)
- description (swe and eng)
- resourceShortName (swe and eng)
- identifier (name of meta data file)
- downloadLocation (meningsmängder) (if installed on k2)
- downloadLocation (statistics)
- executionLocation (link to korp)
- samplesLocation (location of meta data file)
- metadataCreationDate
- sizeInfo (tokens and sentences)

Make sure to have the correct iprHolder and metadataCreator in your templatefile, as well as all the required xml-tags.\n"""

    # parse command line options
    for opt, value in opts:
        if opt == "-t":
            templatexml = value
        if opt == "-c":
            configfile = value
        if opt == "-h":
            print helpmsg_long
            sys.exit(0)

    if not configfile:
        print helpmsg
        sys.exit(0)

    if not templatexml:
        print helpmsg
        sys.exit(0)

    # parse config file
    corpuslist = list(parse_config(configfile))

    # make new metadata xml
    for args, line in corpuslist:
        corpus = make_meta_xml(templatexml, args, line)

        # Must convert this script to python 3 before this can work
        # # update corpus_statistics
        # outxml = "../" + corpus + ".xml"
        # os.system("python update-corpus-stats.py " + outxml)


def parse_config(configfile):
    with codecs.open(configfile, "r", "UTF-8") as c:
        for n, line in enumerate(c.readlines()):
            if line.strip() and not line.startswith("#"):
                line = line.replace("\t", "  ")
                args = line.split("  ")
                args = [a.strip() for a in args if a.strip()]
                # asserterror = "Wrong number of arguments in %s, line %s" %(configfile, n)
                # assert (len(args) == 6), asserterror
                yield args, n


def has_export(exportfile):
    """Check if an exportfile is installed on k2."""
    lscommand = 'ssh k2.spraakdata.gu.se ls -l /var/www/html_sb/resurser/meningsmangder/*.bz2'
    process = subprocess.Popen(lscommand.split(), stdout=subprocess.PIPE)
    output = process.communicate()[0].split("\n")
    files = set([line.strip().rsplit(" ", 3)[-1].split("/")[-1] for line in output if line.strip()])

    if exportfile in files:
        return True
    else:
        return False


def make_meta_xml(templatexml, args, line):
    # args[0] == "a": parallel corpus, ASPAC style
    # args[0] == "e": parallel corpus, Europarl style
    if args[0] == "a" or args[0] == "e":
        parallel = args[0]
        _parallel, corpus, lang, lang_short, lang_long, name_en, name_sv, mode, description_en, description_sv = args
        corpus_sv = corpus + "-" + "sv"
        corpus_2 = corpus + "-" + lang_short
        if parallel == "e":
            filename = corpus + "-sv" + lang_short

    else:
        parallel = False
        asserterror = "Wrong number of arguments in configfile, line %s" % line
        # assert (len(args) == 6), asserterror
        if len(args) == 6:
            corpus, name_en, name_sv, mode, description_en, description_sv = args
        elif len(args) == 4:
            corpus, name_en, name_sv, mode = args
            description_en = description_sv = ''
        else:
            raise Exception(asserterror)

    # parse template xml
    xml = etree.parse(templatexml)
    ns = "{http://www.ilsp.gr/META-XMLSchema}"
    # prevent etree from printing namespaces in the resulting xml file
    etree.register_namespace("", "http://www.ilsp.gr/META-XMLSchema")

    # idenfification info
    identificationInfo = xml.find(ns + 'identificationInfo')

    for i in identificationInfo.findall(ns + "resourceName"):
        if i.attrib["lang"] == "eng":
            i.text = name_en
        if i.attrib["lang"] == "swe":
            i.text = name_sv

    for i in identificationInfo.findall(ns + "description"):
        if i.attrib["lang"] == "eng":
            i.text = description_en
        if i.attrib["lang"] == "swe":
            i.text = description_sv

    if parallel:
        for i in identificationInfo.findall(ns + "resourceShortName"):
            if i.attrib["lang"] == "swe":
                i.text = corpus_sv
            else:
                i.attrib["lang"] = lang_long
                i.text = corpus_2
    else:
        for i in identificationInfo.findall(ns + "resourceShortName"):
            i.text = corpus

    if parallel == "e":
        identificationInfo.find(ns + "identifier").text = corpus_2
    else:
        identificationInfo.find(ns + "identifier").text = corpus

    # distribution info
    distributionInfo = xml.find(ns + 'distributionInfo')
    if parallel:
        for i in distributionInfo.findall(ns + 'licenceInfo'):
            if i.find("./" + ns + "attributionText") is not None:
                if i.find("./" + ns + "attributionText").text == "this file contains a scrambled version of the Swedish part of the corpus":
                    if has_export(corpus_sv + ".xml.bz2"):
                        i.find("./" + ns + "downloadLocation").text = "http://spraakbanken.gu.se/lb/resurser/meningsmangder/" + corpus_sv + ".xml.bz2"
                elif i.find("./" + ns + "attributionText").text.startswith("this file contains a scrambled version of"):
                    if has_export(corpus_2 + ".xml.bz2"):
                        i.find("./" + ns + "attributionText").text = "this file contains a scrambled version of the %s part of the corpus" % lang
                        i.find("./" + ns + "downloadLocation").text = "http://spraakbanken.gu.se/lb/resurser/meningsmangder/" + corpus_2 + ".xml.bz2"

                elif i.find("./" + ns + "attributionText").text == "this file contains statistics on the Swedish part of the corpus":
                    i.find("./" + ns + "downloadLocation").text = "https://svn.spraakdata.gu.se/sb-arkiv/pub/frekvens/stats_" + corpus_sv.upper() + ".txt"
                elif i.find("./" + ns + "attributionText").text.startswith("this file contains statistics"):
                    i.find("./" + ns + "attributionText").text = "this file contains statistics on the %s part of the corpus" % lang
                    i.find("./" + ns + "downloadLocation").text = "https://svn.spraakdata.gu.se/sb-arkiv/pub/frekvens/stats_" + corpus_2.upper() + ".txt"

            if i.find("./" + ns + "executionLocation") is not None:
                if parallel == "e":
                    i.find(ns + "executionLocation").text = "http://spraakbanken.gu.se/korp/?mode=" + mode + "#corpus=" + corpus_2
                else:
                    i.find(ns + "executionLocation").text = "http://spraakbanken.gu.se/korp/?mode=" + mode + "#corpus=" + corpus_sv

    else:
        for i in distributionInfo.findall(ns + 'licenceInfo'):
            if i.find("./" + ns + "downloadLocation") is not None:
                for x in i.findall(ns + "downloadLocation"):
                    loc = x.text
                    if loc.endswith(".bz2"):
                        if has_export(corpus + ".xml.bz2"):
                            x.text = "http://spraakbanken.gu.se/lb/resurser/meningsmangder/" + corpus + ".xml.bz2"
                    elif loc.endswith(".txt"):
                        x.text = "https://svn.spraakdata.gu.se/sb-arkiv/pub/frekvens/stats_" + corpus.upper() + ".txt"

            if i.find("./" + ns + "executionLocation") is not None:
                if mode == "modern":
                    i.find(ns + "executionLocation").text = "http://spraakbanken.gu.se/korp/#corpus=" + corpus
                else:
                    i.find(ns + "executionLocation").text = "http://spraakbanken.gu.se/korp/?mode=" + mode + "#corpus=" + corpus

    # language info
    if parallel:
        for i in xml.findall(".//" + ns + 'languageInfo'):
            if i.find(ns + "languageId").text != "swe":
                i.find(ns + "languageId").text = lang_long
                i.find(ns + "languageName").text = lang

    # xml location
    resourceDocumentationInfo = xml.find(ns + "resourceDocumentationInfo")
    if parallel == "e":
        resourceDocumentationInfo.find(ns + "samplesLocation").text = "http://spraakbanken.gu.se/eng/resource/" + filename
    else:
        resourceDocumentationInfo.find(ns + "samplesLocation").text = "http://spraakbanken.gu.se/eng/resource/" + corpus

    # creation date
    date = str(time.strftime("%Y-%m-%d"))
    metadataInfo = xml.find(ns + "metadataInfo")
    metadataInfo.find(ns + "metadataCreationDate").text = date

    # write new xml
    if parallel == "e":
        outxml = OUTPATH + filename + ".xml"
        print "writing file", outxml
        xml.write(outxml, encoding="UTF-8")
        return filename
    else:
        outxml = OUTPATH + corpus + ".xml"
        print "writing file", outxml
        xml.write(outxml, encoding="UTF-8")
        return corpus


if __name__ == "__main__":
    main(sys.argv[1:])
