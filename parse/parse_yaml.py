"""Read YAML metadata files, compile and prepare information for the API."""

import argparse
import datetime
import json
import traceback
from collections import defaultdict
from pathlib import Path

import requests
import yaml
from translate_lang import get_lang_names


STATIC_DIR = Path("../metadata_api/static")
YAML_DIR = Path("../yaml")
OUT_RESOURCE_TEXTS = STATIC_DIR / "resource-texts.json"

# Instatiate command line arg parser
parser = argparse.ArgumentParser(description="Read YAML metadata files, compile and prepare information for the API")
parser.add_argument("--debug", action="store_true", help="Print debug info")
parser.add_argument("--offline", action="store_true", help="Skip getting file info for downloadables")


def main(resource_types=["collection", "lexicon", "corpus", "model"], debug=False, offline=False):
    """Read YAML metadata files, compile and prepare information for the API (main wrapper)."""
    resource_ids = []
    all_resources = {}
    resource_texts = defaultdict(dict)
    collection_mappings = {}

    for resource_type in resource_types:
        if debug:
            print(f"Processing {resource_type} resources")
        # Get resources from yaml
        yaml_resources = get_yaml(YAML_DIR / resource_type, resource_texts, collection_mappings,
                                  resource_type, debug=debug, offline=offline)
        # Get resource-text-mapping
        resource_ids.extend(list(yaml_resources.keys()))
        # Save result in all_resources
        all_resources.update(yaml_resources)

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
            write_json(STATIC_DIR / f"{resource_type}.json", res_json)
    write_json(STATIC_DIR / "collection.json", collection_json)


def get_yaml(directory, resource_texts, collections, res_type, debug=False, offline=False):
    """Gather all yaml resource files of one type, update resource texts and collections dict."""
    resources = {}

    for filepath in sorted(Path(directory).iterdir()):
        if not filepath.suffix == ".yaml":
            continue

        try:
            if debug:
                print(f"  Processing {filepath}")
            with open(filepath, encoding="utf-8") as f:
                res = yaml.load(f, Loader=yaml.FullLoader)
                fileid = filepath.stem
                new_res = {"id": fileid}

                # Update resouce_texts and remove long_descriptions for now
                if res.get("description", {}).get("swe", "").strip():
                    resource_texts[fileid]["swe"] = res["description"]["swe"]
                if res.get("description", {}).get("eng", "").strip():
                    resource_texts[fileid]["eng"] = res["description"]["eng"]
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
                                    "name": {
                                        "swe": swedish_name,
                                        "eng": english_name
                                    }
                                })
                        except LookupError:
                            print(f"Error: Could not find language code {langcode} (resource: {fileid})")
                res["languages"] = langs
                res.pop("language_codes", "")

                if not offline:
                    # Add file info for downloadables
                    for d in res.get("downloads", []):
                        url = d.get("url")
                        if url and not ("size" in d and "last-modified" in d):
                            size, date = get_download_metadata(url, fileid, res_type)
                            d["size"] = size
                            d["last-modified"] = date

                new_res.update(res)
                resources[fileid] = new_res

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

        except Exception as e:
            print(f"Error: failed to process '{filepath}'")
            print(traceback.format_exc())

    return resources


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


def get_download_metadata(url, name, res_type):
    """Check headers of file from url and return the file size and last modified date."""
    res = requests.head(url)
    size = res.headers.get("Content-Length")
    date = res.headers.get("Last-Modified")
    if date:
        date = datetime.datetime.strptime(date, "%a, %d %b %Y %H:%M:%S %Z").strftime("%Y-%m-%d")
    if res.status_code == 404:
        print(f"Error: Could not find downloadable for {res_type} '{name}': {url}")
    return size, date


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
    main(debug=args.debug, offline=args.offline)
