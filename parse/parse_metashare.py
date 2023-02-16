"""Parse Meta Share files and store info as json."""

import argparse
import datetime
import json
import os
import sys
import traceback
from collections import defaultdict
from xml.etree import ElementTree as etree

import requests
from blacklist import BLACKLIST
from licence import licence_name, licence_url
from trainingdata import TRAININGDATA
from translate_lang import translate

# https://svn.spraakdata.gu.se/sb-arkiv/pub/metadata/
STATIC_DIR = "../metadata/static"
IN_RESOURCE_TEXTS = "../meta-share/resource-texts"
OUT_RESOURCE_TEXTS = "../metadata/static/resource-texts.json"

IO_RESOURCES = {
    "corpus": ("../json_old/corpus", "../meta-share/corpus", "../metadata/static/corpora.json"),
    "lexicon": ("../json_old/lexicon", "../meta-share/lexicon", "../metadata/static/lexicons.json"),
    "model": ("../json_old/model", "../meta-share/model", "../metadata/static/models.json"),
}

METASHAREURL = "https://svn.spraakdata.gu.se/sb-arkiv/pub/metadata/"
METASHARE_LICENCE = "CC BY 4.0"
METASHARE_RESTRICTION = "attribution"


# Instatiate command line arg parser
parser = argparse.ArgumentParser(description="Parse Meta Share files and store info as json")
parser.add_argument("--debug", action="store_true", help="Print debug info")


def main(resource_types=["corpus", "lexicon", "model"], debug=False):
    """Parse Meta Share files and store info as json (main wrapper)."""
    # Create static dir if it does not exist
    if not os.path.isdir(STATIC_DIR):
        os.makedirs(STATIC_DIR)

    resource_ids = []
    all_resources = {}
    resource_texts = defaultdict(dict)
    collections = defaultdict(dict)

    for resource_type in resource_types:
        # Get resources from json and complete from metashare
        json_resources = get_json(IO_RESOURCES.get(resource_type)[0], resource_texts, collections[resource_type],
                                  resource_type, debug=debug)
        json_resources.update(parse_metashare(IO_RESOURCES.get(resource_type)[1], json_resources, resource_type,
                              debug=debug))
        # Get resource-text-mapping
        resource_ids.extend(list(json_resources.keys()))
        # Add sizes and resource-lists to collections
        update_collections(collections[resource_type], json_resources)
        # Save result in all_resources
        # Sort alphabetically by key
        json_resources = dict(sorted(json_resources.items()))
        all_resources[resource_type] = json_resources

    # Get resource texts and dump them as json
    resource_mappings = get_resource_text_mappings(resource_ids)
    read_resource_texts(resource_mappings, resource_texts)
    write_json(OUT_RESOURCE_TEXTS, resource_texts)

    # Set has_description for every resource and save as json
    for resource_type in resource_types:
        set_description_bool(all_resources[resource_type], resource_texts)
        write_json(IO_RESOURCES.get(resource_type)[2], all_resources[resource_type])


def update_collections(type_collection, resources):
    """Add sizes and resource-lists to collections."""
    for collection, res_list in type_collection.items():
        col = resources.get(collection)
        if not col:
            print(f"ERROR: Collection '{collection}' is not defined was referenced by the following resource: "
                  f"{', '.join(res_list)}. Removing collection from these resources.")
            for res_id in res_list:
                res = resources.get(res_id, {})
                col_list = res.get("in_collections", [])
                col_list.remove(collection)
                if not col_list:
                    res.pop("in_collections")
            continue

        col_id = col.get("id")
        if col:
            col["size"] = col.get("size", {})
            col["size"]["resources"] = str(len(res_list))
            col["resources"] = res_list

            # Add in_collections info to json of the collection's resources
            for res_id in res_list:
                res_item = resources.get(res_id)
                if res_item and col_id not in res_item.get("in_collections", []):
                        res_item["in_collections"] = res_item.get("in_collections", [])
                        res_item["in_collections"].append(col_id)


def get_json(directory, resource_texts, type_collections, res_type, debug=False):
    """Gather all json resource files of one type, update resource texts and collections dict."""
    resources = {}

    for filename in sorted(os.listdir(directory)):
        if not filename.endswith(".json"):
            continue

        path = os.path.join(directory, filename)
        with open(path) as f:
            res = json.load(f)
            fileid = filename.split(".")[0]

            # Skip if item is blacklisted
            if fileid in BLACKLIST[res_type]:
                if debug:
                    print("Skipping black-listed resource", fileid)
                continue

            # Replace some null values with empty strings for consistency
            for i in ["description_sv", "description_en", "name_sv", "name_en"]:
                if res.get(i) is None:
                    res[i] = ""

            # Update resouce_texts and remove long_descriptions for now
            if res.get("long_description_sv"):
                resource_texts[fileid]["sv"] = res["long_description_sv"]
            if res.get("long_description_en"):
                resource_texts[fileid]["en"] = res["long_description_en"]
            res.pop("long_description_sv", None)
            res.pop("long_description_en", None)

            # Add file info for downloadables
            for d in res.get("downloads", []):
                url = d.get("download")
                if url and not ("size" in d and "last-modified" in d):
                    size, date = get_download_metadata(url, fileid, res_type)
                    d["size"] = size
                    d["last-modified"] = date

            resources[fileid] = res

            # Update collections dict
            if res.get("collection") == True:
                type_collections[fileid] = type_collections.get(fileid, [])
                if res.get("resources"):
                    type_collections[fileid].extend(res["resources"])

            if res.get("in_collections"):
                for collection_id in res["in_collections"]:
                    type_collections[collection_id] = type_collections.get(collection_id, [])
                    type_collections[collection_id].append(fileid)

    return resources


def parse_metashare(directory, json_resources, res_type, debug=False):
    """Parse the meta share files and return as JSON object."""
    resources = {}

    for filename in sorted(os.listdir(directory)):
        if not filename.endswith(".xml"):
            continue

        # Use file ID (instead of resource ID in META-SHARE) because things break for parallel corpora otherwise
        fileid = filename.split(".")[0]

        if fileid in json_resources:
            if debug:
                print("Skipping META-SHARE for resource {}. Found JSON instead!".format(fileid))
            continue

        path = os.path.join(directory, filename)
        resource = {}
        name_sv = ""
        name_en = ""
        description_sv = ""
        description_en = ""
        lang = ""

        # Parse xml
        try:
            xml = etree.parse(path)
            ns = "{http://www.ilsp.gr/META-XMLSchema}"
            # prevent etree from printing namespaces in the resulting xml file
            etree.register_namespace("", "http://www.ilsp.gr/META-XMLSchema")

            # Get idenfification info
            identificationInfo = xml.find(ns + "identificationInfo")

            # Get identifier
            # shortname = identificationInfo.find(ns + "resourceShortName")
            # resources[shortname.text] = resource
            # resources[shortname.text]["id"] = shortname.text

            # Skip if item is blacklisted
            if fileid in BLACKLIST[res_type]:
                if debug:
                    print("Skipping black-listed resource", fileid)
                continue

            resources[fileid] = resource
            resources[fileid]["id"] = fileid

            resource["type"] = res_type

            # Add info on whether resource is marked as training data
            resource["trainingdata"] = fileid in TRAININGDATA[res_type]

            # Get language
            if res_type == "model":
                lang = xml.findall(".//" + ns + "inputInfo")
            else:
                lang = xml.findall(".//" + ns + "languageInfo")
            resource["lang"] = []
            for i in lang:
                lang_dict = {}
                lang_dict["code"] = i.find(ns + "languageId").text
                if i.find(ns + "languageName") is not None:
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
                distro = {}
                licence_el = i.find(ns + "licence")
                if licence_el is not None:
                    distro["licence"] = licence_name(licence_el.text)
                    version_el = i.find(ns + "version")
                    if version_el is not None:
                        distro["licence"] += ' ' + version_el.text
                    elif distro["licence"][:2] == 'CC':
                        # Default version for CC is 4.0
                        distro["licence"] += ' 4.0'
                    if licence_url(licence_el.text):
                        distro["licence_url"] = licence_url(licence_el.text)
                if i.find(ns + "restrictionsOfUse") is not None:
                    distro["restriction"] = i.find(ns + "restrictionsOfUse").text
                if i.find(ns + "attributionText") is not None:
                    distro["info"] = i.find(ns + "attributionText").text

                access_medium = i.find(ns + "distributionAccessMedium")
                if access_medium is not None:
                    if access_medium.text == "downloadable" and i.find(ns + "downloadLocation") is not None:
                        url = i.find(ns + "downloadLocation").text
                        if url:
                            resource["downloads"].append(distro)
                            distro["download"] = url
                            download_type, fmt = get_download_type(url)
                            distro["type"] = download_type
                            distro["format"] = fmt
                            size, date = get_download_metadata(url, fileid, res_type)
                            distro["size"] = size
                            distro["last-modified"] = date
                    elif access_medium.text == "accessibleThroughInterface" and i.find(ns + "executionLocation") is not None:
                        resource["interface"].append(distro)
                        distro["access"] = i.find(ns + "executionLocation").text
                    elif access_medium.text == "other":
                        if i.find(ns + "executionLocation") is not None:
                            resource["interface"].append(distro)
                            distro["access"] = i.find(ns + "executionLocation").text
                        elif i.find(ns + "downloadLocation") is not None:
                            url = i.find(ns + "downloadLocation").text
                            if url:
                                resource["downloads"].append(distro)
                                distro["download"] = url
                                download_type, fmt = get_download_type(url)
                                distro["type"] = download_type
                                distro["format"] = fmt
                                size, date = get_download_metadata(url, fileid, res_type)
                                distro["size"] = size
                                distro["last-modified"] = date

            # Add location of meta data file
            metashare_url = METASHAREURL + res_type + "/" + filename
            size, date = get_download_metadata(metashare_url, fileid, res_type)
            metashare = {
                "licence": METASHARE_LICENCE,
                "restriction": METASHARE_RESTRICTION,
                "download": metashare_url,
                "type": "metadata",
                "format": "METASHARE",
                "size": size,
                "last-modified": date
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

        except Exception:
            print("Failed to process file '{}'.\n".format(path), file=sys.stderr)
            print(traceback.format_exc())

    return resources


def get_download_type(download_path):
    """Get type and format of downloadable from pathname."""
    if "/meningsmangder/" in download_path:
        return "corpus", "XML"
    elif "/frekvens/" in download_path:
        return "token frequencies", "CSV"
    elif "/pub/lmf/" in download_path:
        return "lexicon", "LMF"
    # Display filename
    elif "." in os.path.split(download_path)[-1]:
        filename = os.path.split(download_path)[-1]
        return filename, filename.split(".")[-1]
    else:
        return "other", None


def get_download_metadata(url, name, res_type):
    """Check headers of file from url and return the file size and last modified date."""
    res = requests.head(url)
    size = res.headers.get("Content-Length")
    date = res.headers.get("Last-Modified")
    if date:
        date = datetime.datetime.strptime(date, "%a, %d %b %Y %H:%M:%S %Z").strftime("%Y-%m-%d")
    if res.status_code == 404:
        print(f"Could not find downloadable for {res_type} '{name}': {url}")
    return size, date


def get_resource_texts_files(directory=IN_RESOURCE_TEXTS):
    """Get list of resource text files."""
    resource_text_files = set()
    for filename in sorted(os.listdir(directory)):
        resource_text_files.add(filename)
    return resource_text_files


def get_resource_text_mappings(resource_ids):
    """Read resource description files and create mappings."""
    resource_mappings = {}
    resource_text_files = get_resource_texts_files()
    for i in resource_ids:
        name_sv = i + "_swe.html"
        name_en = i + "_eng.html"
        new_dict = {}
        if name_sv in resource_text_files:
            new_dict["sv"] = [name_sv]

        if name_en in resource_text_files:
            new_dict["en"] = [name_en]

        if new_dict:
            resource_mappings[i] = new_dict

    return resource_mappings


def read_resource_texts(resource_mappings, resource_texts, directory=IN_RESOURCE_TEXTS):
    """Read all resource texts into the 'resource_texts' dict."""
    for res_id, res in resource_mappings.items():
        # Skip resources that recieved their long description from json
        if res_id in resource_texts:
            continue
        new_dict = {}
        # Collect Swedish texts
        sv_list = []
        for i in res.get("sv", []):
            path = os.path.join(directory, i)
            with open(path, "r") as f:
                sv_list.append(f.read())
        if sv_list:
            new_dict["sv"] = "\n".join(sv_list)
        # Collect English texts
        en_list = []
        for i in res.get("en", []):
            path = os.path.join(directory, i)
            with open(path, "r") as f:
                en_list.append(f.read())
        if en_list:
            new_dict["en"] = "\n".join(en_list)
        resource_texts[res_id] = new_dict


def set_description_bool(resources, resource_texts):
    """Add bool 'has_description' for every resource."""
    for i in resources:
        resources[i]["has_description"] = False
        if resources[i].get("long_description_sv") or resources[i].get("long_description_en"):
            resources[i]["has_description"] = True
        if resource_texts.get(i):
            resources[i]["has_description"] = True


def write_json(filename, data):
    """Write as json to a temporary file, and afterwards move the file into place."""
    with open(filename + ".new", "w") as f:
        json.dump(data, f)
    os.rename(filename + ".new", filename)


if __name__ == '__main__':
    args = parser.parse_args()
    main(debug=args.debug)
