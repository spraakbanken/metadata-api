"""
Create META-SHARE format from YAML metadata. Requires >Python 3.8.

META-SHARE documentation: http://www.meta-net.eu/meta-share/META-SHARE%20%20documentationUserManual.pdf
"""

import argparse
import os
import re
import sys
import time
from pathlib import Path

import yaml
# import xml.etree.ElementTree as etree
from lxml import etree  # Using lxml because of the getparent method
from translate_lang import get_lang_names

METASHARE_URL = "http://www.ilsp.gr/META-XMLSchema"
METASHARE_NAMESPACE = f"{{{METASHARE_URL}}}"
SBX_SAMPLES_LOCATION = "https://spraakbanken.gu.se/en/resources/"
METASHARE_TEMPLATES_DIR = "../metadata/metadata_conversions/metashare-templates/"
METASHARE_TEMPLATE = "%s-template.xml"
METASHARE_SCHEMA = "../metadata/metadata_conversions/metashare-templates/META-SHARE-Resource.xsd"
METASHARE_DIR = "../metadata/metadata_conversions/metashare/"
YAML_DIR = "../metadata/yaml/"

SBX_DEFAULT_LICENSE = "CC-BY"
SBX_DEFAULT_RESTRICTION = "attribution"


METASHARE_LICENSES = ["CC-BY", "CC-BY-NC", "CC-BY-NC-ND", "CC-BY-NC-SA", "CC-BY-ND", "CC-BY-SA", "CC-ZERO",
                      "MS-C-NoReD", "MS-C-NoReD-FF", "MS-C-NoReD-ND", "MS-C-NoReD-ND-FF", "MS-NC-NoReD",
                      "MS-NC-NoReD-FF", "MS-NC-NoReD-ND", "MS-NC-NoReD-ND-FF", "MSCommons-BY", "MSCommons-BY-NC",
                      "MSCommons-BY-NC-ND", "MSCommons-BY-NC-SA", "MSCommons-BY-ND", "MSCommons-BY-SA", "CLARIN_ACA",
                      "CLARIN_ACA-NC", "CLARIN_PUB", "CLARIN_RES", "ELRA_END_USER", "ELRA_EVALUATION", "ELRA_VAR",
                      "AGPL", "ApacheLicence_2.0", "BSD", "BSD-style", "GFDL", "GPL", "LGPL", "Princeton_Wordnet",
                      "proprietary", "underNegotiation", "other"]

METASHARE_RESTRICTIONS = ["informLicensor", "redeposit", "onlyMSmembers", "academic-nonCommercialUse", "evaluationUse",
                          "commercialUse", "attribution", "shareAlike", "noDerivatives", "noRedistribution", "other"]


# Instatiate command line arg parser
parser = argparse.ArgumentParser(description="Create and update META-SHARE files from YAML metadata")
parser.add_argument("--debug", action="store_true", help="Print debug info")
parser.add_argument("--validate", action="store_true", help="Validate metashare files upon creation")


def main(validate=False, debug=False):
    """Loop through all yaml files, create missing metashare files and update outdated ones."""
    metasharelist = list(i.stem for i in Path(METASHARE_DIR).glob("**/*.xml"))
    yamldir = Path(YAML_DIR)
    for thisdir in yamldir.glob("*/"):
        if thisdir.stem not in ["corpus", "lexicon", "model"]:
            continue
        for f in sorted(thisdir.glob("*.yaml")):
            if f.stem not in metasharelist:
                out = Path(METASHARE_DIR) / thisdir.stem / f"{f.stem}.xml"
                create_metashare(f, out, debug)
            else:
                metashare_path = Path(METASHARE_DIR) / f.parts[3] / (f.stem + ".xml")
                yaml_time = os.path.getmtime(f)
                metashare_time = os.path.getmtime(metashare_path)
                if yaml_time > metashare_time:
                    update_metashare(f, metashare_path, debug)
                if validate:
                    validate_meta_share(metashare_path)


def create_metashare(yaml_path, out=None, debug=False):
    """Create META-SHARE format from yaml metadata."""
    # Read yaml metadata
    with open(yaml_path, encoding="utf-8") as f:
        yaml_metadata = yaml.safe_load(f)

    # Skip unlisted resources
    if yaml_metadata.get("unlisted") == True:
        if debug:
            print(f"Skipping unlisted resource {yaml_path.stem}")
        return

    res_id = yaml_path.stem
    res_type = yaml_metadata.get("type")

    # Parse template and handle META SHARE namespace
    xml = etree.parse(METASHARE_TEMPLATES_DIR / Path(METASHARE_TEMPLATE % res_type)).getroot()
    # etree.register_namespace("", METASHARE_URL) # Needed when using xml.etree.ElementTree
    ns = METASHARE_NAMESPACE

    # Set idenfification info
    identificationInfo = xml.find(ns + "identificationInfo")
    for i in identificationInfo.findall(ns + "resourceShortName"):
        i.text = res_id
    identificationInfo.find(ns + "identifier").text = res_id

    # Set name
    _set_text(identificationInfo.findall(ns + "resourceName"), yaml_metadata.get("name", {}).get("swe", ""), "swe")
    _set_text(identificationInfo.findall(ns + "resourceName"), yaml_metadata.get("name", {}).get("eng", ""), "eng")

    # Set description
    _set_text(identificationInfo.findall(ns + "description"), yaml_metadata.get("short_description", {}).get("swe", ""), "swe")
    _set_text(identificationInfo.findall(ns + "description"), yaml_metadata.get("short_description", {}).get("eng", ""), "eng")

    # Set metadata creation date in metadataInfo
    xml.find(".//" + ns + "metadataCreationDate").text = str(time.strftime("%Y-%m-%d"))

    # Set availability
    # TODO not represented in yaml yet
    xml.find(".//" + ns + "availability").text = "available-unrestrictedUse"

    # Set licenceInfos
    distInfo = xml.find(".//" + ns + "distributionInfo")
    for d in yaml_metadata.get("downloads", []):
        _set_licence_info(d, distInfo)
    ms_download = {
            "url": f"https://svn.spraakdata.gu.se/sb-arkiv/pub/metadata/{res_type}/{res_id}.xml",
            "licence": SBX_DEFAULT_LICENSE,
            "restriction": "attribution",
        }
    for i in yaml_metadata.get("interface", []):
        _set_licence_info(i, distInfo, download=False)
    _set_licence_info(ms_download, distInfo)

    # Set contactPerson
    _set_contact_info(yaml_metadata.get("contact_info", {}), xml.find(".//" + ns + "contactPerson"))

    # Set samplesLocation
    xml.find(".//" + ns + "samplesLocation").text = f"{SBX_SAMPLES_LOCATION}{res_id}"

    # Set lingualityType
    # TODO not represented in yaml yet
    xml.find(".//" + ns + "lingualityType").text = "monolingual"  # monolingual, bilingual, multilingual

    if res_type == "lexicon":
        # TODO not represented in yaml yet
        # wordList, computationalLexicon, ontology, wordnet, thesaurus, framenet, terminologicalResource, machineReadableDictionary, lexicon
        xml.find(".//" + ns + "lexicalConceptualResourceType").text = "computationalLexicon"

    # Set languageInfo (languageId, languageName)
    # if res_type in ["corpus", "lexicon"]: ??
    _set_language_info(yaml_metadata.get("language_codes", []), xml, yaml_path)

    # Set sizeInfo
    if res_type == "corpus":
        sizeInfos = xml.findall(".//" + ns + "sizeInfo")
        sizeInfos[0].find(ns + "size").text = str(yaml_metadata.get("size", {}).get("tokens", "0"))
        sizeInfos[1].find(ns + "size").text = str(yaml_metadata.get("size", {}).get("sentences", "0"))
    elif res_type == "lexicon":
        sizeInfos = xml.findall(".//" + ns + "sizeInfo")
        sizeInfos[0].find(ns + "size").text = str(yaml_metadata.get("size", {}).get("entries", "0"))

    output = _dump_with_comment(xml)

    # Write XML to file
    with open(out, mode="w", encoding="utf-8") as outfile:
        outfile.write(output)
    if debug:
        print(f"Created META-SHARE {out}")


def update_metashare(yaml_path, metashare_path, debug=False):
    """Update metashare with newer information from YAML metadata."""
    # Read yaml metadata
    with open(yaml_path, encoding="utf-8") as f:
        yaml_metadata = yaml.safe_load(f)

    res_id = yaml_path.stem
    res_type = yaml_metadata.get("type")

    # Parse metashare and handle META SHARE namespace
    xml = etree.parse(metashare_path).getroot()
    output1 = _dump_with_comment(xml)

    # etree.register_namespace("", METASHARE_URL) # Needed when using xml.etree.ElementTree
    ns = METASHARE_NAMESPACE

    # Update names and descriptions
    identificationInfo = xml.find(ns + "identificationInfo")
    _set_text(identificationInfo.findall(ns + "resourceName"), yaml_metadata.get("name", {}).get("swe", ""), "swe")
    _set_text(identificationInfo.findall(ns + "resourceName"), yaml_metadata.get("name", {}).get("eng", ""), "eng")
    _set_text(identificationInfo.findall(ns + "description"), yaml_metadata.get("short_description", {}).get("swe", ""), "swe")
    _set_text(identificationInfo.findall(ns + "description"), yaml_metadata.get("short_description", {}).get("eng", ""), "eng")

    # Update licenceInfos
    distInfo = xml.find(".//" + ns + "distributionInfo")
    for l in distInfo.findall(ns + "licenceInfo"):
        distInfo.remove(l)
    for d in yaml_metadata.get("downloads", []):
        _set_licence_info(d, distInfo)
    ms_download = {
            "url": f"https://svn.spraakdata.gu.se/sb-arkiv/pub/metadata/{res_type}/{res_id}.xml",
            "licence": SBX_DEFAULT_LICENSE,
            "restriction": "attribution",
        }
    for i in yaml_metadata.get("interface", []):
        _set_licence_info(i, distInfo, download=False)
    _set_licence_info(ms_download, distInfo)

    # Update contactPerson
    _update_contact_person(yaml_metadata.get("contact_info", {}), xml.find(".//" + ns + "contactPerson"))

    # Update languageInfo (languageId, languageName)
    if res_type in ["corpus", "lexicon"]:
        _set_language_info(yaml_metadata.get("language_codes", []), xml, yaml_path)

    # Update sizeInfo
    if res_type == "corpus":
        sizeInfos = xml.findall(".//" + ns + "sizeInfo")
        if sizeInfos and len(sizeInfos) == 2:
            if yaml_metadata.get("size", {}).get("tokens"):
                sizeInfos[0].find(ns + "size").text = str(yaml_metadata.get("size", {}).get("tokens"))
            if yaml_metadata.get("size", {}).get("sentences"):
                sizeInfos[1].find(ns + "size").text = str(yaml_metadata.get("size", {}).get("sentences"))
    elif res_type == "lexicon":
        sizeInfos = xml.findall(".//" + ns + "sizeInfo")
        if sizeInfos and yaml_metadata.get("size", {}).get("entries"):
            sizeInfos[0].find(ns + "size").text = str(yaml_metadata.get("size", {}).get("entries", "0"))

    output = _dump_with_comment(xml)
    if output != output1:
        # Write XML to file
        with open(metashare_path, mode="w", encoding="utf-8") as outfile:
            outfile.write(output)
        if debug:
            print(f"Updated META-SHARE {metashare_path}")


def _set_text(elems, text, lang):
    """Set text for elems to 'text' for the correct language."""
    for i in elems:
        if i.attrib["lang"] == lang:
            i.text = text


def _set_licence_info(item, distInfo, download=True):
    """Create licenceInfo trees for item and append them to distInfo."""
    def fix_license(license_str):
        """Try to format license str so it's META-SHARE compatible."""
        if license_str == "CC BY 4.0":
            return SBX_DEFAULT_LICENSE
        if re.match(r"(.+) \d\.\d", license_str):
            license_str = re.sub(r"^(.+) \d\.\d$", r"\1", license_str)
            license_str = license_str.replace(" ", "-")
        if license_str not in METASHARE_LICENSES:
            license_str = "other"
        return license_str

    ns = METASHARE_NAMESPACE
    # Create licenseInfo element
    licenseInfo = etree.Element(ns + "licenceInfo")
    licence = etree.SubElement(licenseInfo, ns + "licence")
    licence.text = fix_license(item.get("licence", item.get("licence", SBX_DEFAULT_LICENSE)))
    restrictionsOfUse = etree.SubElement(licenseInfo, ns + "restrictionsOfUse")
    restrictionsOfUse.text = item.get("restriction", SBX_DEFAULT_RESTRICTION)
    if restrictionsOfUse.text not in METASHARE_RESTRICTIONS:
        restrictionsOfUse.text = "other"
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
    contactPerson.find(ns + "surname").text = name.split()[1] if len(name.split()) > 1 else name.split()[0]
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


def _update_contact_person(contact, contactPerson):
    """Set contact info in contactPerson element."""
    ns = METASHARE_NAMESPACE
    name = contact.get("name") or "Markus Forsberg"
    contactPerson.find(ns + "surname").text = name.split()[1] if len(name.split()) > 1 else name.split()[0]
    contactPerson.find(ns + "givenName").text = name.split()[0]
    contactPerson.find(ns + "communicationInfo" + "/" + ns + "email").text = contact.get("email", "")
    # Create affiliation element if needed
    if contact.get("affiliation") and any(i in contact.get("affiliation", {}) for i in ["organisation", "email"]):
        affiliation = contactPerson.find(ns + "affiliation")
        if affiliation is not None:
            affiliation.find(ns + "organizationName").text = contact["affiliation"].get("organisation", "")
            affiliation.find(ns + "communicationInfo" + "/" + ns + "email").text = contact["affiliation"].get("email", "")
        else:
            affiliation = etree.Element(ns + "affiliation")
            if contact["affiliation"].get("organisation"):
                organizationName = etree.SubElement(affiliation, ns + "organizationName")
                organizationName.text = contact["affiliation"].get("organisation", "")
            if contact["affiliation"].get("email"):
                communicationInfo = etree.SubElement(affiliation, ns + "communicationInfo")
                email = etree.SubElement(communicationInfo, ns + "email")
                email.text = contact["affiliation"].get("email", "")
            _append_pretty(contactPerson, affiliation)

def _set_language_info(language_codes, xml, yaml_path):
    ns = METASHARE_NAMESPACE
    langinfos = list(xml.findall(".//" + ns + "languageInfo"))
    for n, langcode in enumerate(language_codes):
        if n <= len(langinfos) - 1:
            try:
                english_name, _ = get_lang_names(langcode)
                langinfos[n].find(".//" + ns + "languageId").text = langcode
                langinfos[n].find(".//" + ns + "languageName").text = english_name
            except LookupError:
                sys.stderr.write(f"Could not find language code {langcode} (resource: {yaml_path})")
        else:
            # Create new elemets for other languages
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
                sys.stderr.write(f"Could not find language code {langcode} (resource: {yaml_path})")


def _dump_with_comment(xml):
    # Dump XML and hack in autogen comment (etree cannot do this for us and lxml will uglify)
    comment = "This file was automatically generated. Do not make changes directly to this file"\
              " as they might get overwritten."
    xml_string = etree.tostring(xml, encoding="UTF-8", xml_declaration=True).decode("utf-8")
    xml_lines = xml_string.split("\n")
    xml_lines.insert(1, f"<!-- {comment} -->")
    return "\n".join(xml_lines)


def validate_meta_share(filepath):
    """Validate uploaded XML against META-SHARE xsd schema."""
    xml_doc = etree.parse(filepath)
    try:
        XMLSCHEMA.assertValid(xml_doc)
    except Exception as e:
        errormsg = str(e).replace("{http://www.ilsp.gr/META-XMLSchema}", "")
        sys.stderr.write(f"\n{filepath.name}: {errormsg}")


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
    args = parser.parse_args()

    if args.validate:
        XMLSCHEMA_DOC = etree.parse(METASHARE_SCHEMA)
        XMLSCHEMA = etree.XMLSchema(XMLSCHEMA_DOC)

    main(validate=args.validate, debug=args.debug)
