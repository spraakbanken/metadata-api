"""
Create META-SHARE format from json metadata. Requires >Python 3.8.

Meta Share documentation: http://www.meta-net.eu/meta-share/META-SHARE%20%20documentationUserManual.pdf
"""

import json
import time
from pathlib import Path

# import xml.etree.ElementTree as etree
from lxml import etree # Using lxml because of the getparent method

from translate_lang import get_lang_names



METASHARE_URL = "http://www.ilsp.gr/META-XMLSchema"
METASHARE_NAMESPACE = f"{{{METASHARE_URL}}}"
SBX_SAMPLES_LOCATION = "https://spraakbanken.gu.se/en/resources/"
SBX_METASHARE_TEMPLATE = "%s-template.xml"
METASHARE_DIR = "../meta-share/"
JSON_DIR = "../json/"

SBX_DEFAULT_LICENSE = "CC BY 4.0"
SBX_DEFAULT_RESTRICTION = "attribution"

# AUTO_TOKEN = ["segment.token", "stanza.token", "freeling.token", "stanford.token"]
# AUTO_SENT = ["segment.sentence", "stanza.sentence", "freeling.sentence", "stanfort.sentence"]
# AUTO_POS = ["hunpos.pos", "hunpos.msd", "hunpos.msd_hist", "hist.homograph_set", "stanza.pos", "stanza.msd",
#             "stanza.upos", "misc.upos", "flair.pos", "flair.msd", "freeling.pos", "stanford.pos"]
# AUTO_BASEFORM = ["saldo.baseform", "hist.baseform", "freeling.baseform", "treetagger.baseform", "stanford.baseform"]


def wrapper():
    """Loop through all json files and create metashare if it does not exist."""
    metasharelist = list(i.stem for i in Path(METASHARE_DIR).glob("**/*.xml"))
    jsondir = Path(JSON_DIR)
    for thisdir in jsondir.glob("*/"):
        if thisdir.stem not in ["corpus", "lexicon", "model"]:
            continue
        for f in thisdir.glob("*.json"):
            if f.stem not in metasharelist:
                out = Path(METASHARE_DIR) / thisdir.stem / f"{f.stem}.xml"
                create_metashare(f, out)


def create_metashare(json_path, out=None):
    """Create META-SHARE format from json metadata."""
    # Read json metadata
    with open(json_path) as f:
        json_metadata = json.load(f)

    # Skip unlisted resources
    if json_metadata.get("unlisted") == True:
        print(f"Skipping unlisted resource {json_path.stem}")
        return

    res_id = json_path.stem
    res_type = json_metadata.get("type")

    # Parse template and handle META SHARE namespace
    xml = etree.parse("templates" / Path(SBX_METASHARE_TEMPLATE % res_type)).getroot()
    # etree.register_namespace("", METASHARE_URL) # Needed when using xml.etree.ElementTree
    ns = METASHARE_NAMESPACE

    # Set resource type
    resourceType = xml.find(ns + "resourceComponentType").find(ns + "corpusInfo").find(ns + "resourceType")
    resourceType.text = "toolService" if res_type == "model" else res_type

    # Set idenfification info
    identificationInfo = xml.find(ns + "identificationInfo")
    for i in identificationInfo.findall(ns + "resourceShortName"):
        i.text = res_id
    identificationInfo.find(ns + "identifier").text = res_id

    # Set name
    _set_text(identificationInfo.findall(ns + "resourceName"), json_metadata.get("name", {}).get("swe", ""), "swe")
    _set_text(identificationInfo.findall(ns + "resourceName"), json_metadata.get("name", {}).get("eng", ""), "eng")

    # Set description
    _set_text(identificationInfo.findall(ns + "description"), json_metadata.get("short_description", {}).get("swe", ""), "swe")
    _set_text(identificationInfo.findall(ns + "description"), json_metadata.get("short_description", {}).get("eng", ""), "eng")

    # Set metadata creation date in metadataInfo
    xml.find(".//" + ns + "metadataCreationDate").text = str(time.strftime("%Y-%m-%d"))

    # Set availability
    # TODO not represented in json yet
    xml.find(".//" + ns + "availability").text = "available-unrestrictedUse"

    # Set licenceInfos
    distInfo = xml.find(".//" + ns + "distributionInfo")
    for d in json_metadata.get("downloads", []):
        _set_licence_info(d, distInfo)
    ms_download = {
            "url": f"https://svn.spraakdata.gu.se/sb-arkiv/pub/metadata/{res_type}/{res_id}.xml",
            "licence": "CC BY 4.0",
            "restriction": "attribution",
        }
    _set_licence_info(ms_download, distInfo)
    for i in json_metadata.get("interface", []):
        _set_licence_info(i, distInfo, download=False)

    # Set contactPerson
    _set_contact_info(json_metadata.get("contact_info", {}), xml.find(".//" + ns + "contactPerson"))

    # Set samplesLocation
    xml.find(".//" + ns + "samplesLocation").text = f"{SBX_SAMPLES_LOCATION}{res_id}"

    # Set lingualityType
    # TODO not represented in json yet
    xml.find(".//" + ns + "lingualityType").text = "monolingual"  # monolingual, bilingual, multilingual

    if res_type == "lexicon":
        # TODO not represented in json yet
        # wordList, computationalLexicon, ontology, wordnet, thesaurus, framenet, terminologicalResource, machineReadableDictionary, lexicon
        xml.find(".//" + ns + "lexicalConceptualResourceType").text = "computationalLexicon"

    # Set languageInfo (languageId, languageName)
    langs = json_metadata.get("language_codes", [])
    if langs:
        # Fill in info for first language
        langcode = langs[0]
        try:
            english_name, _ = get_lang_names(langcode)
            xml.find(".//" + ns + "languageId").text = langcode
            xml.find(".//" + ns + "languageName").text = english_name
        except LookupError:
            print(f"Could not find language code {langcode} (resource: {json_path})")
    if len(langs) > 1:
        # Create new elemets for other languages
        for langcode in langs[1:]:
            try:
                english_name, _ = get_lang_names(langcode)
                # Create languageInfo element
                languageInfo = etree.Element(ns + "languageInfo")
                languageId = etree.SubElement(languageInfo, ns + "languageId")
                languageId.text = langcode
                languageName = etree.SubElement(languageInfo, ns + "languageName")
                languageName.text = english_name
                # Prettify element
                indent_xml(languageInfo, level=5)
                # Insert after after last languageInfo
                parent = xml.find(".//" + ns + "languageInfo").getparent()
                i = list(parent).index(parent.findall(ns + "languageInfo")[-1])
                parent.insert(i + 1, languageInfo)
            except LookupError:
                print(f"Could not find language code {langcode} (resource: {json_path})")

    # Set sizeInfo
    if res_type == "corpus":
        sizeInfos = xml.findall(".//" + ns + "sizeInfo")
        sizeInfos[0].find(ns + "size").text = json_metadata.get("size", {}).get("tokens", "0")
        sizeInfos[1].find(ns + "size").text = json_metadata.get("size", {}).get("sentences", "0")
    elif res_type == "lexicon":
        sizeInfos = xml.findall(".//" + ns + "sizeInfo")
        sizeInfos[0].find(ns + "size").text = json_metadata.get("size", {}).get("entries", "0")

    # Dump XML and hack in autogen comment (etree cannot do this for us and lxml will uglify)
    comment = "This file was automatically generated. Do not make changes directly to this file"\
              " as they will get overwritten."
    xml_string = etree.tostring(xml, encoding="UTF-8", xml_declaration=True).decode("utf-8")
    xml_lines = xml_string.split("\n")
    xml_lines.insert(1, f"<!-- {comment} -->")
    output = "\n".join(xml_lines)

    # Write XML to file
    with open(out, mode="w", encoding="utf-8") as outfile:
        outfile.write(output)
    print(f"written {out}")


def _set_text(elems, text, lang):
    """Set text for elems to 'text' for the correct language."""
    for i in elems:
        if i.attrib["lang"] == lang:
            i.text = text


def _set_licence_info(item, distInfo, download=True):
    """Create licenceInfo trees for item and append them to distInfo."""
    ns = METASHARE_NAMESPACE
    # Create licenseInfo element
    licenseInfo = etree.Element(ns + "licenceInfo")
    licence = etree.SubElement(licenseInfo, ns + "licence")
    licence.text = item.get("licence", item.get("licence", SBX_DEFAULT_LICENSE))
    restrictionsOfUse = etree.SubElement(licenseInfo, ns + "restrictionsOfUse")
    restrictionsOfUse.text = item.get("restriction", SBX_DEFAULT_RESTRICTION)
    if download:
        distributionAccessMedium = etree.SubElement(licenseInfo, ns + "distributionAccessMedium")
        distributionAccessMedium.text = "downloadable"
        downloadLocation = etree.SubElement(licenseInfo, ns + "downloadLocation")
        downloadLocation.text = item.get("url", "")
    else:
        distributionAccessMedium = etree.SubElement(licenseInfo, ns + "distributionAccessMedium")
        distributionAccessMedium.text = "accessibleThroughInterface"
        executionLocation = etree.SubElement(licenseInfo, ns + "executionLocation")
        executionLocation.text = item.get("access", "")
    if item.get("info", None):
        attributionText = etree.SubElement(licenseInfo, ns + "attributionText")
        attributionText.text = item.get("info", "")
    # Prettify element
    indent_xml(licenseInfo, level=2)
    # Insert in position 1 or after last licenceInfo
    if distInfo.find(ns + "licenceInfo") is None:
        distInfo.insert(1, licenseInfo)
    else:
        # Get index of last licenceInfo
        i = list(distInfo).index(distInfo.findall(ns + "licenceInfo")[-1])
        distInfo.insert(i + 1, licenseInfo)


def _set_contact_info(contact, contactPerson):
    """Set contact info in contactPerson element."""
    ns = METASHARE_NAMESPACE
    name = contact.get("name") or "Markus Forsberg"
    contactPerson.find(ns + "surname").text = name.split()[1] if len(name) > 1 else name.split()[0]
    contactPerson.find(ns + "givenName").text = name.split()[0]
    contactPerson.find(ns + "communicationInfo" + "/" + ns + "email").text = contact.get("email", "")
    # Create affiliation element if needed
    if contact.get("affiliation") and any(i in contact.get("affiliation", {}) for i in ["organisation", "email"]):
        affiliation = etree.Element(ns + "affiliation")
        if contact["affiliation"].get("organisation"):
            organizationName = etree.SubElement(affiliation, ns + "organizationName")
            organizationName.text = contact["affiliation"].get("organisation", "")
        if contact["affiliation"].get("email"):
            communicationInfo = etree.SubElement(affiliation, ns + "communicationInfo")
            email = etree.SubElement(communicationInfo, ns + "email")
            email.text = contact["affiliation"].get("email", "")
        _append_pretty(contactPerson, affiliation)


def _append_pretty(parent, child):
    """Append child to parent and hack indentation."""
    # Calculate indentation level for child (NB: works only if child has siblings!)
    level = int(len((list(parent)[-1].tail).strip("\n")) / 2 + 1)
    indent_xml(child, level)
    list(parent)[-1].tail = "\n" + "  " * level
    child.tail = "\n" + "  " * (level - 1)
    parent.append(child)


def indent_xml(elem, level=0, indentation="  ") -> None:
    """Add pretty-print indentation to XML tree.

    From http://effbot.org/zone/element-lib.htm#prettyprint
    """
    i = "\n" + level * indentation
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + indentation
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
        for elem in elem:
            indent_xml(elem, level + 1)
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i


if __name__ == "__main__":
    wrapper()

    # # For tesning purposes:
    # import sys
    # filename = sys.argv[1]
    # create_metashare(filename)

    # create_metashare(Path("../json/corpus/abotidning.json"), Path("test-abotidning.xml"))
    # create_metashare(Path("../json/corpus/aspacsvbe.json"), Path("test-aspacsvbe.xml"))
