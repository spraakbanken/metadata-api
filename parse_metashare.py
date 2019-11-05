"""Parse Meta Share files and store info as json."""

import json
import os
from xml.etree import ElementTree as etree

from translate_lang import translate

# https://svn.spraakdata.gu.se/sb-arkiv/pub/metadata/
STATIC_DIR = "metadata/static"
METASHAREURL = "https://svn.spraakdata.gu.se/sb-arkiv/pub/metadata/"


def parse_metashare(directory, type=None):
    """Parse the meta share files and return as JSON object."""
    resources = {}

    for filename in os.listdir(directory):
        if not filename.endswith(".xml"):
            continue

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
        resources[shortname.text]["id"] = shortname.text

        resource["type"] = type

        # Get language
        lang = xml.findall(".//" + ns + "languageInfo")
        resource["lang"] = []
        for i in lang:
            l = {}
            l["code"] = i.find(ns + "languageId").text
            l["name_en"] = i.find(ns + "languageName").text
            l["name_sv"] = translate(i.find(ns + "languageName").text)
            resource["lang"].append(l)

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

        # Get distribution info
        distributionInfo = xml.find(ns + "distributionInfo")
        resource["downloads"] = []
        resource["interface"] = []
        for i in distributionInfo.findall(ns + "licenceInfo"):
            if i.find(ns + "downloadLocation") is not None:
                distro = {}
                resource["downloads"].append(distro)
                distro["licence"] = i.find(ns + "licence").text
                distro["restriction"] = i.find(ns + "restrictionsOfUse").text
                distro["download"] = i.find(ns + "downloadLocation").text
                if i.find(ns + "attributionText") is not None:
                    distro["info"] = i.find(ns + "attributionText").text
            if i.find(ns + "executionLocation") is not None:
                distro = {}
                resource["interface"].append(distro)
                distro["licence"] = i.find(ns + "licence").text
                distro["restriction"] = i.find(ns + "restrictionsOfUse").text
                distro["access"] = i.find(ns + "executionLocation").text

        # Get contact person
        contactPerson = xml.find(ns + "contactPerson")
        resource["contact_info"] = {}
        resource["contact_info"]["surname"] = contactPerson.find(ns + "surname").text
        resource["contact_info"]["givenName"] = contactPerson.find(ns + "givenName").text
        resource["contact_info"]["email"] = contactPerson.find(ns + "communicationInfo").find(ns + "email").text
        resource["contact_info"]["affiliation"] = {}
        resource["contact_info"]["affiliation"]["organisation"] = contactPerson.find(ns + "affiliation").find(ns + "organizationName").text
        resource["contact_info"]["affiliation"]["email"] = contactPerson.find(ns + "affiliation").find(ns + "communicationInfo").find(ns + "email").text

        # Get size info
        sizes = xml.findall(".//" + ns + "sizeInfo")
        resource["size"] = {}
        for i in sizes:
            unit = i.find(ns + "sizeUnit").text
            resource["size"][unit] = i.find(ns + "size").text

        # Add location of meta data file
        resource["meta_share_location"] = METASHAREURL + type + "/" + filename

    return resources


if __name__ == '__main__':

    # Create static dir if it does not exist
    if not os.path.isdir(STATIC_DIR):
        os.makedirs(STATIC_DIR)

    corpora = parse_metashare("meta-share/corpus", type="corpus")
    with open("metadata/static/corpora.json", "w") as f:
        json.dump(corpora, f)

    lexicons = parse_metashare("meta-share/lexicon", type="lexicon")
    with open("metadata/static/lexicons.json", "w") as f:
        json.dump(lexicons, f)
