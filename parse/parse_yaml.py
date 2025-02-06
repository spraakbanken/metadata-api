"""Read YAML metadata files, compile and prepare information for the API."""

from __future__ import annotations

import argparse
import datetime
import json
import sys
from collections import defaultdict
from pathlib import Path

import jsonschema
import requests
import yaml
from translate_lang import get_lang_names

STATIC_DIR = Path("../metadata_api/static")
YAML_DIR = Path("../metadata/yaml")
SCHEMA_DIR = Path("../metadata/schema")
LOCALIZATIONS_DIR = Path("../metadata/localizations")
OUT_RESOURCE_TEXTS = STATIC_DIR / "resource-texts.json"

# Instatiate command line arg parser
parser = argparse.ArgumentParser(description="Read YAML metadata files, compile and prepare information for the API")
parser.add_argument("--debug", action="store_true", help="Print debug info")
parser.add_argument("--offline", action="store_true", help="Skip getting file info for downloadables")
parser.add_argument("--validate", action="store_true", help="Validate metadata using schema")


def main(
    resource_types: list[str] | None = None, debug: bool = False, offline: bool = False, validate: bool = False
) -> None:
    """Read YAML metadata files, compile and prepare information for the API (main wrapper).

    Args:
        resource_types: List of resource types to process.
        debug: Print debug info.
        offline: Skip getting file info for downloadables.
        validate: Validate metadata using schema.
    """
    if resource_types is None:
        resource_types = ["lexicon", "corpus", "model", "analysis", "utility"]
    resource_ids = []
    all_resources = {}
    resource_texts = defaultdict(dict)
    collection_mappings = {}
    localizations = get_localizations()

    if validate:
        resource_schema = get_schema(SCHEMA_DIR / "metadata.json")
        # YAML safe_load() - handle dates as strings
        yaml.constructor.SafeConstructor.yaml_constructors["tag:yaml.org,2002:timestamp"] = (
            yaml.constructor.SafeConstructor.yaml_constructors["tag:yaml.org,2002:str"]
        )
    else:
        resource_schema = None

    for filepath in sorted(YAML_DIR.glob("**/*.yaml")):
        # Get resources from yaml
        yaml_resources = get_yaml(
            filepath,
            resource_texts,
            collection_mappings,
            resource_schema,
            localizations,
            debug=debug,
            offline=offline,
            validate=validate,
        )
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
        res_json = {k: v for k, v in all_resources.items() if v.get("type", "") == resource_type}
        set_description_bool(res_json, resource_texts)
        write_json(STATIC_DIR / f"{resource_type}.json", res_json)
    write_json(STATIC_DIR / "collection.json", collection_json)


def get_schema(filepath: Path) -> dict:
    """Load and return the JSON schema from the given file path.

    Args:
        filepath: Path to the JSON schema file.

    Returns:
        The loaded JSON schema.
    """
    try:
        with filepath.open() as schema_file:
            schema = json.load(schema_file)
    except Exception:
        print(f"Error: failed to get schema '{filepath}'", file=sys.stderr)
        schema = None

    return schema


def get_yaml(
    filepath: Path,
    resource_texts: defaultdict,
    collections: dict,
    resource_schema: dict,
    localizations: dict,
    debug: bool = False,
    offline: bool = False,
    validate: bool = False,
) -> dict:
    """Gather all YAML resource files of one type, update resource texts and collections dict.

    Args:
        filepath: Path to the YAML file.
        resource_texts: Dictionary to store resource texts.
        collections: Dictionary to store collections.
        resource_schema: JSON schema for validation.
        localizations: Dictionary of localizations.
        debug: Print debug info.
        offline: Skip getting file info for downloadables.
        validate: Validate metadata using schema.

    Returns:
        Dictionary of resources.
    """
    resources = {}
    add_resource = True

    try:
        if debug:
            print(f"  Processing {filepath}")
        with filepath.open(encoding="utf-8") as f:
            res = yaml.safe_load(f)
            fileid = filepath.stem

            res_type = res.get("type")
            # Validate YAML (unless it is an analysis or utility https://github.com/spraakbanken/metadata/issues/7)
            if validate and res_type not in {"analysis", "utility"} and resource_schema is not None:
                try:
                    jsonschema.validate(instance=res, schema=resource_schema)
                except jsonschema.exceptions.ValidationError as e:
                    print(f"Error: validation error for {fileid}: {e.message}", file=sys.stderr)
                    add_resource = False
                except Exception:
                    print(f"Something went wrong when validating for {fileid}", file=sys.stderr)
                    add_resource = False

            if add_resource:
                new_res = {"id": fileid}
                # Make sure size attrs only contain numbers
                for k, v in res.get("size", {}).items():
                    if not str(v).isdigit():
                        res["size"][k] = 0

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
                            langs.append({"code": langcode, "name": {"swe": swedish_name, "eng": english_name}})
                        except LookupError:
                            print(f"Error: Could not find language code {langcode} (resource: {fileid})",
                                  file=sys.stderr)
                res["languages"] = langs
                res.pop("language_codes", "")

                # Add localizations to data
                for loc_name, loc in localizations.items():
                    if loc_name in res:
                        key_eng = res.get(loc_name, "")
                        res[loc_name] = {"eng": key_eng, "swe": loc.get(key_eng, "")}

                if not offline:
                    # Add file info for downloadables
                    for d in res.get("downloads", []):
                        url = d.get("url")
                        if url and "size" not in d and "last-modified" not in d:
                            size, date = get_download_metadata(url, fileid, res_type)
                            d["size"] = size
                            d["last-modified"] = date

                new_res.update(res)
                resources[fileid] = new_res

                # Update collections dict
                if res.get("collection") is True:
                    collections[fileid] = collections.get(fileid, [])
                    if res.get("resources"):
                        collections[fileid].extend(res["resources"])
                        collections[fileid] = sorted(set(collections[fileid]))

                if res.get("in_collections"):
                    for collection_id in res["in_collections"]:
                        collections[collection_id] = collections.get(collection_id, [])
                        collections[collection_id].append(fileid)
                        collections[collection_id] = sorted(set(collections[collection_id]))

    except Exception as e:
        print(f"Error: failed to process '{filepath}': {e}", file=sys.stderr)

    return resources


def update_collections(collection_mappings: dict, collection_json: dict, all_resources: dict) -> None:
    """Add sizes and resource-lists to collections.

    Args:
        collection_mappings: Mappings of collections to resources.
        collection_json: JSON data of collections.
        all_resources: Dictionary of all resources.
    """
    for collection, res_list in collection_mappings.items():
        col = collection_json.get(collection)
        if not col:
            print(
                f"Error: Collection '{collection}' is not defined but was referenced by the following resource: "
                f"{', '.join(res_list)}. Removing collection from these resources.",
                file=sys.stderr
            )
            for res_id in res_list:
                res = all_resources.get(res_id, {})
                col_list = res.get("in_collections", [])
                col_list.remove(collection)
                if not col_list:
                    res.pop("in_collections")
            continue

        # Remove resource IDs for non-existing resources
        new_res_list = [i for i in res_list if i in all_resources]

        col_id = col.get("id")
        if col:
            col["size"] = col.get("size", {})
            col["size"]["resources"] = len(new_res_list)
            col["resources"] = new_res_list

            # Add in_collections info to json of the collection's resources
            for res_id in new_res_list:
                res_item = all_resources.get(res_id)
                if res_item and col_id not in res_item.get("in_collections", []):
                    res_item["in_collections"] = res_item.get("in_collections", [])
                    res_item["in_collections"].append(col_id)


def get_download_metadata(url: str, name: str, res_type: str) -> tuple[int, str]:
    """Check headers of file from URL and return the file size and last modified date.

    Args:
        url: URL of the downloadable file.
        name: Name of the resource.
        res_type: Type of the resource.

    Returns:
        File size and last modified date.
    """
    try:
        res = requests.head(url)
        size = int(res.headers.get("Content-Length")) if res.headers.get("Content-Length") else None
        date = res.headers.get("Last-Modified")
        if date:
            date = datetime.datetime.strptime(date, "%a, %d %b %Y %H:%M:%S %Z").strftime("%Y-%m-%d")
        if res.status_code == 404:  # noqa: PLR2004
            print(f"Error: Could not find downloadable for {res_type} '{name}': {url}", file=sys.stderr)
    except Exception:
        print(f"Error: Could not get downloadable '{name}': {url}", file=sys.stderr)
        # Set to some kind of neutral values
        size = 0
        date = datetime.today().strftime("%Y-%m-%d")
    return size, date


def set_description_bool(resources: dict, resource_texts: defaultdict) -> None:
    """Add bool 'has_description' for every resource.

    Args:
        resources: Dictionary of resources.
        resource_texts: Dictionary of resource texts.
    """
    for resource in resources.values():
        resource["has_description"] = False
        if resource.get("description"):
            resource["has_description"] = True
        if resource_texts.get(resource["id"]):
            resource["has_description"] = True


def get_localizations() -> dict:
    """Read localizations from YAML files.

    Returns:
        Localizations as a dictionary.
    """
    localizations = {}
    for filepath in LOCALIZATIONS_DIR.glob("**/*.yaml"):
        loc_name = filepath.stem
        with filepath.open(encoding="utf-8") as f:
            loc = yaml.safe_load(f)
            if isinstance(loc, dict):
                localizations[loc_name] = loc
    return localizations


def write_json(filename: Path, data: dict) -> None:
    """Write data as JSON to a temporary file, and afterwards move the file into place.

    Args:
        filename: Path to the output JSON file.
        data: Data to be written as JSON.
    """
    outfile = Path(filename)
    outfile.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = outfile.parent / (outfile.name + ".new")
    with tmp_path.open("w") as f:
        json.dump(data, f, default=str)
    tmp_path.rename(filename)


if __name__ == "__main__":
    args = parser.parse_args()
    main(debug=args.debug, offline=args.offline, validate=args.validate)
