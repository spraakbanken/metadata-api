"""Read YAML metadata files, compile and prepare information for the API."""

from __future__ import annotations

import datetime
import gettext
import json
import logging
from collections import defaultdict
from pathlib import Path

import jsonschema
import pycountry
import requests
import yaml
from flask import Config
from jsonschema.exceptions import ValidationError

# Swedish translations for language names
SWEDISH = gettext.translation("iso639-3", pycountry.LOCALES_DIR, languages=["sv"])

logger = logging.getLogger("parse_yaml")


def process_resources(
    resource_paths: list[str] | None = None,
    debug: bool = False,
    offline: bool = False,
    validate: bool = False,
    config_obj: Config | dict | None = None,
) -> None:
    """Read YAML metadata files, compile and prepare information for the API (main wrapper).

    Args:
        resource_paths: List of specific resource to reprocess (["resource_type/resource_id"]).
            This list may contain deleted resources which will then be removed from the API.
        debug: Print debug info.
        offline: Skip getting file info for downloadables.
        validate: Validate metadata using schema.
        config_obj: Configuration object or dictionary.
    """
    if config_obj is None:
        raise ValueError("Configuration object is required")

    # Convert config_obj to dict if it is a Config object
    if isinstance(config_obj, Config):
        config_obj = {key: config_obj[key] for key in config_obj}

    resource_types = [Path(i).stem for i in config_obj["RESOURCES"].values()]
    all_resources = {}
    resource_texts = defaultdict(dict)
    resource_text_file = Path(config_obj["STATIC"]) / config_obj["RESOURCE_TEXTS_FILE"]
    collections_file = Path(config_obj["STATIC"]) / config_obj["COLLECTIONS_FILE"]
    collection_mappings = {}
    metadata_dir = Path(config_obj["METADATA_DIR"])
    if config_obj is None:
        raise ValueError("Configuration object is required")
    localizations = get_localizations(metadata_dir / config_obj["LOCALIZATIONS_DIR"])

    failed_files = []

    if debug:
        logger.setLevel(logging.DEBUG)

    if validate:
        resource_schema = get_schema(metadata_dir / config_obj["SCHEMA_FILE"])
        # YAML safe_load() - handle dates as strings
        yaml.constructor.SafeConstructor.yaml_constructors["tag:yaml.org,2002:timestamp"] = (
            yaml.constructor.SafeConstructor.yaml_constructors["tag:yaml.org,2002:str"]
        )
    else:
        resource_schema = None

    if not resource_paths:
        filepaths = sorted((metadata_dir / config_obj["YAML_DIR"]).rglob("*.yaml"))
    else:
        # When processing a single YAML file: set filepaths and load existing resource data
        filepaths = [metadata_dir / config_obj["YAML_DIR"] / f"{i}.yaml" for i in resource_paths]

        for resource_type in resource_types:
            with (Path(config_obj["STATIC"]) / f"{resource_type}.json").open(encoding="utf-8") as f:
                all_resources.update(json.load(f))
        with resource_text_file.open(encoding="utf-8") as f:
            resource_texts.update(json.load(f))
        with collections_file.open(encoding="utf-8") as f:
            collections_data = json.load(f)
            collection_mappings = {k: v.get("resources", []) for k, v in collections_data.items()}

    # Process YAML file(s) and update all_resources, collection_mappings, and resource_texts
    for filepath in filepaths:
        resource_id, resource_dict, success = process_yaml_file(
            filepath,
            resource_texts,
            collection_mappings,
            resource_schema,
            localizations,
            offline=offline,
            validate=validate,
        )
        if not resource_dict:
            # Resource dict is emtpty: file was deleted and should be removed from the data
            all_resources.pop(resource_id, None)
        else:
            all_resources[resource_id] = resource_dict
        if success is False:
            failed_files.append(str(Path(filepath.parent.name) / filepath.stem))

    # Sort alphabetically by key
    all_resources = dict(sorted(all_resources.items()))

    # Get collections data from all_resources and update collections with sizes and resource lists
    collections_data = {k: v for k, v in all_resources.items() if v.get("collection")}
    update_collections(collection_mappings, collections_data, all_resources)
    write_json(collections_file, collections_data)

    # Dump resource texts as json
    write_json(resource_text_file, resource_texts)

    # Update resource json files
    for resource_type in resource_types:
        res_json = {k: v for k, v in all_resources.items() if v.get("type", "") == resource_type}
        # Set has_description for every resource and save as json.
        set_description_bool(res_json, resource_texts)
        write_json(Path(config_obj["STATIC"]) / f"{resource_type}.json", res_json)

    messages = []
    if failed_files:
        messages.append(f"Failed to process: {', '.join(failed_files)}")
    if resource_paths and len(resource_paths) == 1 and not failed_files:
        messages.append(f"Updated resource {resource_paths[0]}")
    elif resource_paths and len(resource_paths) > 1:
        messages.append(f"Updated resources: {', '.join(resource_paths)}")
    else:
        messages.append("Updated all resources")
    message = ". ".join(messages) + "."
    logger.info(message)


def process_yaml_file(
    filepath: Path,
    resource_texts: defaultdict,
    collection_mappings: dict,
    resource_schema: dict | None,
    localizations: dict,
    offline: bool = False,
    validate: bool = False,
) -> tuple[str, dict, bool]:
    """Process a single YAML file and extract/process resource information.

    Update collection_mappings, and resource_texts.

    Args:
        filepath: Path to the YAML file.
        resource_texts: Dictionary to store resource texts.
        collection_mappings: Mapping from collection IDs to a list of resource IDs {collection_id: [resource_id, ...]}
        resource_schema: JSON schema for validation.
        localizations: Dictionary of localizations.
        offline: Skip getting file info for downloadables.
        validate: Validate metadata using schema.

    Returns:
        The ID of the resource, the processed resource data and a bool stating whether the process was successful.
    """
    fileid = filepath.stem
    success = True

    # If file does not exist, remove resource from resource_texts and collection_mappings and return empty dict
    if not filepath.exists():
        resource_texts.pop(fileid, None)

        # Remove from collection_mappings in case this file is a collection
        # If this resource is part of a collection it will be removed automatically by update_collections() later.
        collection_mappings.pop(fileid, None)

        logger.info("Removed resource '%s'", filepath)
        return fileid, {}, success

    try:
        processed_resource = {}
        logger.debug("Processing '%s'", filepath)
        with filepath.open(encoding="utf-8") as f:
            res = yaml.safe_load(f)
            res_type = res.get("type", "")

            # Validate YAML
            if validate and resource_schema is not None:
                try:
                    jsonschema.validate(instance=res, schema=resource_schema)
                except ValidationError as e:
                    logger.error("Validation error for '%s/%s': %s", res_type, fileid, e.message)
                    return fileid, {}, False
                except Exception:
                    logger.exception("Something went wrong when validating for '%s/%s'", res_type, fileid)
                    return fileid, {}, False

            processed_resource = {"id": fileid}
            # Make sure size attrs only contain numbers
            for k, v in res.get("size", {}).items():
                if not str(v).isdigit():
                    res["size"][k] = 0

            # Update resouce_texts and remove descriptions for now
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
                        logger.error("Could not find language code '%s' (resource: '%s')", langcode, fileid)
            res["languages"] = langs
            res.pop("language_codes", "")

            # Add localizations to data
            for loc_name, loc in localizations.items():
                if loc_name in res:
                    key_eng = res.get(loc_name, "")
                    res[loc_name] = {"eng": key_eng, "swe": loc.get(key_eng, key_eng)}

            if not offline:
                # Add file info for downloadables
                for d in res.get("downloads", []):
                    url = d.get("url")
                    if url and "size" not in d and "last-modified" not in d:
                        size, date = get_download_metadata(url, fileid)
                        d["size"] = size
                        d["last-modified"] = date

            processed_resource.update(res)

            # Update collections dict
            if res.get("collection") is True:
                collection_mappings[fileid] = collection_mappings.get(fileid, [])
                if res.get("resources"):
                    collection_mappings[fileid].extend(res["resources"])
                    collection_mappings[fileid] = sorted(set(collection_mappings[fileid]))

            if res.get("in_collections"):
                for collection_id in res["in_collections"]:
                    collection_mappings[collection_id] = collection_mappings.get(collection_id, [])
                    collection_mappings[collection_id].append(fileid)
                    collection_mappings[collection_id] = sorted(set(collection_mappings[collection_id]))

    except Exception:
        logger.exception("Failed to process '%s'", filepath)

    return fileid, processed_resource, success


def update_collections(collection_mappings: dict, collections_data: dict, all_resources: dict) -> None:
    """Add sizes and resource lists to collections.

    Args:
        collection_mappings: Mappings of collections to resources.
        collections_data: JSON data of collections.
        all_resources: Dictionary containing the data of all resources.
    """
    for collection, res_list in collection_mappings.items():
        col = collections_data.get(collection)
        if not col:
            logger.warning(
                "Collection '%s' is not defined but was referenced by the following resource: %s. "
                "Removing collection from these resources.",
                collection,
                ", ".join(res_list),
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
        removed_resources = list(set(res_list).difference(set(new_res_list)))
        if removed_resources and len(removed_resources) == 1:
            logger.warning(
                "The resource '%s' does not exist and was removed from the '%s' collection.",
                removed_resources[0],
                collection,
            )
        elif removed_resources:
            logger.warning(
                "The following resources do not exist and were removed from the '%s' collection: %s.",
                collection,
                ", ".join(removed_resources),
            )

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


def get_schema(filepath: Path) -> dict | None:
    """Load and return the JSON schema from the given file path.

    Args:
        filepath: Path to the JSON schema file.

    Returns:
        The loaded JSON schema.
    """
    try:
        with filepath.open(encoding="utf-8") as schema_file:
            schema = json.load(schema_file)
    except Exception:
        logger.exception("Failed to get schema '%s'", filepath)
        schema = None

    return schema


def get_download_metadata(url: str, name: str) -> tuple[int | None, str | None]:
    """Check headers of file from URL and return the file size and last modified date.

    Args:
        url: URL of the downloadable file.
        name: Name of the resource.

    Returns:
        File size and last modified date.
    """
    # Set to some kind of neutral values which are used in case of an error
    size = 0
    date = ""

    try:
        res = requests.head(url)
        content_length = res.headers.get("Content-Length")
        size = int(content_length) if content_length is not None else None
        date = res.headers.get("Last-Modified")
        if date:
            date = datetime.datetime.strptime(date, "%a, %d %b %Y %H:%M:%S %Z").strftime("%Y-%m-%d")
        if res.status_code == 404:  # noqa: PLR2004
            logger.error("Could not find downloadable for '%s': %s", name, url)
    except Exception:
        logger.exception("Could not get downloadable '%s': %s", name, url)
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


def get_localizations(localizations_dir: Path) -> dict:
    """Read localizations from YAML files.

    Args:
        localizations_dir: Path to the directory containing localization files.

    Returns:
        Localizations as a dictionary.
    """
    localizations = {}
    for filepath in localizations_dir.rglob("*.yaml"):
        loc_name = filepath.stem
        with filepath.open(encoding="utf-8") as f:
            loc = yaml.safe_load(f)
            if isinstance(loc, dict):
                localizations[loc_name] = loc
    return localizations


def get_lang_names(langcode: str) -> tuple[str, str]:
    """Get English and Swedish name for language represented by langcode.

    Args:
        langcode: The ISO 639-3 language code.

    Returns:
        A tuple containing the English and Swedish names of the language.
    """
    l = pycountry.languages.get(alpha_3=langcode)
    if l is None:
        raise LookupError
    english_name = l.name
    swedish_name = SWEDISH.gettext(english_name).lower()
    return english_name, swedish_name


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
    logger.debug("Wrote '%s'", filename)


if __name__ == "__main__":
    import argparse
    import sys

    # Add the parent directory to the system path to import config or config_default
    sys.path.append(str(Path(__file__).resolve().parent.parent))
    import config_default
    config_dict = {k: v for k, v in vars(config_default).items() if not k.startswith("__")}
    try:
        import config
        config_dict.update({k: v for k, v in vars(config).items() if not k.startswith("__")})
    except ImportError:
        pass
    config_dict["STATIC"] = Path(__file__).resolve().parent / "static"

    # Configure logging
    LOG_FORMAT = "%(levelname)s - %(message)s"
    logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)

    # Instatiate command line arg parser
    parser = argparse.ArgumentParser(description="Compile and prepare YAML metadata for the API")
    parser.add_argument("--debug", action="store_true", help="Print debug info")
    parser.add_argument("--offline", action="store_true", help="Skip getting file info for downloadables")
    parser.add_argument("--validate", action="store_true", help="Validate metadata using schema")
    parser.add_argument(
        "--resource-path", type=str, help="Comma-separated paths to the resources to update (format: 'type/id')"
    )

    # Parse command line arguments
    args = parser.parse_args()

    process_resources(
        resource_paths=args.resource_path.split(",") if args.resource_path else None,
        debug=args.debug,
        offline=args.offline,
        validate=args.validate,
        config_obj=config_dict,
    )
