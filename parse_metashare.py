"""Parse Meta Share files and store info as json."""

import json
import os
from xml.etree import ElementTree as etree

from translate_lang import translate
from resource_text_mapping import resource_mappings

# https://svn.spraakdata.gu.se/sb-arkiv/pub/metadata/
STATIC_DIR = "metadata/static"
METASHAREURL = "https://svn.spraakdata.gu.se/sb-arkiv/pub/metadata/"
METASHARE_LICENCE = "CC-BY"
METASHARE_RESTRICTION = "attribution"


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
            lang_dict = {}
            lang_dict["code"] = i.find(ns + "languageId").text
            lang_dict["name_en"] = i.find(ns + "languageName").text
            lang_dict["name_sv"] = translate(i.find(ns + "languageName").text)
            resource["lang"].append(lang_dict)

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
                if i.find(ns + "downloadLocation").text:
                    download_type, format = get_download_type(i.find(ns + "downloadLocation").text)
                    distro["type"] = download_type
                    distro["format"] = format
            if i.find(ns + "executionLocation") is not None:
                distro = {}
                resource["interface"].append(distro)
                distro["licence"] = i.find(ns + "licence").text
                distro["restriction"] = i.find(ns + "restrictionsOfUse").text
                distro["access"] = i.find(ns + "executionLocation").text

        # Add location of meta data file
        metashare = {
            "licence": METASHARE_LICENCE,
            "restriction": METASHARE_RESTRICTION,
            "download": METASHAREURL + type + "/" + filename,
            "type": "metadata",
            "format": "METASHARE"
        }
        resource["downloads"].append(metashare)

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

    return resources


def get_download_type(download_path):
    """Get type and format of downloadable from pathname."""
    if "/meningsmangder/" in download_path:
        return "corpus", "XML"
    elif "/frekvens/" in download_path:
        return "token frequencies", "CSV"
    elif "/pub/lmf/" in download_path:
        return "lexicon", "LMF"
    else:
        return "other", None


def read_resource_texts(directory="meta-share/resource-texts"):
    """Read all resource texts into a dictionary."""
    resource_texts = {}
    for res_id, res in resource_mappings.items():
        new_dict = {}
        # Collect Swedish texts
        for i in res.get("sv", []):
            new_list = []
            path = os.path.join(directory, i)
            with open(path, "r") as f:
                new_list.append(f.read())
        new_dict["sv"] = "\n".join(new_list)
        # Collect English texts
        for i in res.get("en", []):
            new_list = []
            path = os.path.join(directory, i)
            with open(path, "r") as f:
                new_list.append(f.read())
        new_dict["en"] = "\n".join(new_list)
        resource_texts[res_id] = new_dict

    return resource_texts


def get_resource_texts_files(directory="meta-share/resource-texts"):
    """Get list of resource text files."""
    resource_text_files = set()
    for filename in sorted(os.listdir(directory)):
        resource_text_files.add(filename)
    return resource_text_files


def extend_resource_text_mapping(resource_ids):
    """Extend resource_mappings with files that follow naming standard."""
    resource_text_files = get_resource_texts_files()
    for i in resource_ids:
        if i not in resource_mappings:
            name_sv = i + "_swe.html"
            name_en = i + "_eng.html"
            new_dict = {}
            if name_sv in resource_text_files:
                new_dict["sv"] = [name_sv]
            if name_en in resource_text_files:
                new_dict["en"] = [name_en]
            if new_dict:
                resource_mappings[i] = new_dict


if __name__ == '__main__':

    # Create static dir if it does not exist
    if not os.path.isdir(STATIC_DIR):
        os.makedirs(STATIC_DIR)

    # Get corpora from metashare
    corpora = parse_metashare("meta-share/corpus", type="corpus")
    with open("metadata/static/corpora.json", "w") as f:
        json.dump(corpora, f)

    # Get lexicons from metashare
    lexicons = parse_metashare("meta-share/lexicon", type="lexicon")
    with open("metadata/static/lexicons.json", "w") as f:
        json.dump(lexicons, f)

    # Extend resource-text-mapping
    resource_ids = list(corpora.keys())
    resource_ids.extend(lexicons.keys())
    extend_resource_text_mapping(resource_ids)

    # Get resource texts and dump them as json
    resource_texts = read_resource_texts()
    with open("metadata/static/resource-texts.json", "w") as f:
        json.dump(resource_texts, f)
