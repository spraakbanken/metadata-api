"""Parse Meta Share files and store info as json."""

# https://svn.spraakdata.gu.se/sb-arkiv/pub/metadata/

import os
from xml.etree import ElementTree as etree

import json


def parse_metashare(directory, type=None):
    """Parse the meta share files and return as JSON object."""
    resources = {}

    for filename in os.listdir(directory):
        if not filename.endswith(".xml"):
            continue
        # print(filename)

        path = os.path.join(directory, filename)
        resource = {}
        name_sv = ""
        name_en = ""
        description_sv = ""
        description_en = ""
        lang = ""

        # Parse xml
        xml = etree.parse(path)
        ns = "{http://www.ilsp.gr/META-XMLSchema}"
        # prevent etree from printing namespaces in the resulting xml file
        etree.register_namespace("", "http://www.ilsp.gr/META-XMLSchema")

        # Get idenfification info
        identificationInfo = xml.find(ns + "identificationInfo")

        # Get identifier
        shortname = identificationInfo.find(ns + "resourceShortName")
        resources[shortname.text] = resource

        resource["type"] = type

        # Get name
        for i in identificationInfo.findall(ns + "resourceName"):
            if i.attrib["lang"] == "eng" and i.text:
                name_en = i.text
            if i.attrib["lang"] == "swe":
                name_sv = i.text
        resource["name_sv"] = name_sv
        resource["name_en"] = name_en

        # Get description
        for i in identificationInfo.findall(ns + "description"):
            if i.attrib["lang"] == "eng" and i.text:
                description_en = i.text
            if i.attrib["lang"] == "swe" and i.text:
                description_sv = i.text
        resource["description_sv"] = description_sv
        resource["description_en"] = description_en

        # Get language
        lang = xml.find(".//" + ns + "languageId")
        if lang is not None:
            resource["lang"] = lang.text

    # for i in resources:
    #     print(i)
    return resources


if __name__ == '__main__':

    corpora = parse_metashare("meta-share/corpus", type="corpus")
    with open("metadata/static/corpora.json", "w") as f:
        json.dump(corpora, f)

    lexicons = parse_metashare("meta-share/lexicon", type="lexicon")
    with open("metadata/static/lexicons.json", "w") as f:
        json.dump(lexicons, f)
