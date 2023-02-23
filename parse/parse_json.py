"""Read JSON metadata files, compile and prepare information for the API."""

import argparse
import datetime
import json
from collections import defaultdict
from pathlib import Path

import requests

from translate_lang import get_lang_names

STATIC_DIR = Path("../metadata/static")
JSON_DIR = Path("../json")
OUT_RESOURCE_TEXTS = STATIC_DIR / "resource-texts.json"
IO_RESOURCES = {
    "corpus": (JSON_DIR / "corpus", STATIC_DIR / "corpora.json"),
    "lexicon": (JSON_DIR / "lexicon", STATIC_DIR / "lexicons.json"),
    "model": (JSON_DIR / "model", STATIC_DIR / "models.json"),
    "collection": (JSON_DIR / "collection", STATIC_DIR / "collection.json"),
}

# Instatiate command line arg parser
parser = argparse.ArgumentParser(description="Read JSON metadata files, compile and prepare information for the API")
parser.add_argument("--debug", action="store_true", help="Print debug info")


def main(resource_types=["collection", "lexicon", "corpus", "model"], debug=False):
    """Read JSON metadata files, compile and prepare information for the API (main wrapper)."""
    resource_ids = []
    all_resources = {}
    resource_texts = defaultdict(dict)
    collection_mappings = {}

    for resource_type in resource_types:
        # Get resources from json
        json_resources = get_json(IO_RESOURCES.get(resource_type)[0], resource_texts, collection_mappings,
                                  resource_type, debug=debug)
        # Get resource-text-mapping
        resource_ids.extend(list(json_resources.keys()))
        # Save result in all_resources
        all_resources.update(json_resources)

    # Sort alphabetically by key
    all_resources = dict(sorted(all_resources.items()))

    # Add sizes and resource-lists to collections
    collection_json = {k: v for k, v in all_resources.items() if v.get("collection")}
    update_collections(collection_mappings, collection_json, all_resources)

    # Dump resource texts as json
    write_json(OUT_RESOURCE_TEXTS, resource_texts)

    # Set has_description for every resource and save as json
    for resource_type in resource_types:
        if not resource_type == "collection":
            res_json = {k: v for k, v in all_resources.items() if v.get("type", "") == resource_type}
            set_description_bool(res_json, resource_texts)
            write_json(IO_RESOURCES.get(resource_type)[1], res_json)
    write_json(IO_RESOURCES.get("collection")[1], collection_json)


def update_collections(collection_mappings, collection_json, all_resources):
    """Add sizes and resource-lists to collections."""
    for collection, res_list in collection_mappings.items():
        col = collection_json.get(collection)
        if not col:
            print(f"ERROR: Collection '{collection}' is not defined but was referenced by the following resource: "
                f"{', '.join(res_list)}. Removing collection from these resources.")
            for res_id in res_list:
                res = all_resources.get(res_id, {})
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
                res_item = all_resources.get(res_id)
                if res_item and col_id not in res_item.get("in_collections", []):
                        res_item["in_collections"] = res_item.get("in_collections", [])
                        res_item["in_collections"].append(col_id)


def get_json(directory, resource_texts, collections, res_type, debug=False):
    """Gather all json resource files of one type, update resource texts and collections dict."""
    resources = {}

    for filepath in sorted(Path(directory).iterdir()):
        if not filepath.suffix == ".json":
            continue

        with open(filepath) as f:
            res = json.load(f)
            fileid = filepath.stem
            res["id"] = fileid

            # Translate some attrs to old format:
            res["name_sv"] = res.get("name", {}).get("swe", "")
            res["name_en"] = res.get("name", {}).get("eng", "")
            res.pop("name", None)
            res["description_sv"] = res.get("short_description", {}).get("swe", "")
            res["description_en"] = res.get("short_description", {}).get("eng", "")
            res.pop("short_description", None)
            for d in res.get("downloads", []):
                d["download"] = d["url"]
                d.pop("url", None)
            name = res.get("contact_info", {}).get("name") or "Markus Forsberg"
            res["contact_info"]["surname"] = name.split()[1] if len(name) > 1 else name.split()[0]
            res["contact_info"]["givenName"] = name.split()[0]
            res["contact_info"].pop("name", None)

            # Update resouce_texts and remove long_descriptions for now
            if res.get("description", {}).get("swe"):
                resource_texts[fileid]["sv"] = res["description"]["swe"]
            if res.get("description", {}).get("eng"):
                resource_texts[fileid]["en"] = res["description"]["eng"]
            res.pop("description", None)

            # Get full language info
            langs = res.get("languages", [])
            for langcode in res.get("language_codes", []):
                if langcode not in [l.get("code") for l in langs]:
                    try:
                        english_name, swedish_name = get_lang_names(langcode)
                        langs.append(
                            {
                                "code": langcode,
                                "name_sv": swedish_name,
                                "name_en": english_name
                            })
                    except LookupError:
                        print(f"Could not find language code {langcode} (resource: {fileid})")
            res["lang"] = langs
            res.pop("language_codes", "")

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
                collections[fileid] = collections.get(fileid, [])
                if res.get("resources"):
                    collections[fileid].extend(res["resources"])
                    collections[fileid] = sorted(list(set(collections[fileid])))

            if res.get("in_collections"):
                for collection_id in res["in_collections"]:
                    collections[collection_id] = collections.get(collection_id, [])
                    collections[collection_id].append(fileid)
                    collections[collection_id] = sorted(list(set(collections[collection_id])))

    return resources


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
    outfile = Path(filename)
    outfile.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = outfile.parent / (outfile.name + ".new")
    with open(tmp_path, "w") as f:
        json.dump(data, f)
    tmp_path.rename(filename)


if __name__ == '__main__':
    args = parser.parse_args()
    main(debug=args.debug)
