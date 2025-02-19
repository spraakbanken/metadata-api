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

# Swedish translations for language names
SWEDISH = gettext.translation("iso639-3", pycountry.LOCALES_DIR, languages=["sv"])

logger = logging.getLogger("parse_yaml")


def main(
    resource_paths: list[str] | None = None,
    debug: bool = False,
    offline: bool = False,
    validate: bool = False,
    config_obj: Config | dict | None = None,  # Remove this arg when parse_yaml is no longer used as a script
) -> None:
    """Read YAML metadata files, compile and prepare information for the API (main wrapper).

    Args:
        resource_paths: List of specific resource to reprocess (["resource_type/resource_id"]).
            This list may contain deleted resources which will then be removed from the API.
        debug: Print debug info.
        offline: Skip getting file info for downloadables.
        validate: Validate metadata using schema.
        config_obj: Configuration object.
    """
    resource_types = [Path(i).stem for i in config_obj.get("RESOURCES").values()]
    all_resources = {}
    resource_texts = defaultdict(dict)
    resource_text_file = config_obj.get("STATIC") / config_obj.get("RESOURCE_TEXTS_FILE")
    collections_file = config_obj.get("STATIC") / config_obj.get("COLLECTIONS_FILE")
    collection_mappings = {}
    metadata_dir = Path(config_obj.get("METADATA_DIR"))
    if config_obj is None:
        raise ValueError("Configuration object is required")
    localizations = get_localizations(metadata_dir / config_obj.get("LOCALIZATIONS_DIR"))

    if debug:
        logger.setLevel(logging.DEBUG)

    if validate:
        resource_schema = get_schema(metadata_dir / config_obj.get("SCHEMA_FILE"))
        # YAML safe_load() - handle dates as strings
        yaml.constructor.SafeConstructor.yaml_constructors["tag:yaml.org,2002:timestamp"] = (
            yaml.constructor.SafeConstructor.yaml_constructors["tag:yaml.org,2002:str"]
        )
    else:
        resource_schema = None

    if not resource_paths:
        filepaths = sorted((metadata_dir / config_obj.get("YAML_DIR")).rglob("*.yaml"))
    else:
        # When processing a single YAML file: set filepaths and load existing resource data
        filepaths = [metadata_dir / config_obj.get("YAML_DIR") / f"{i}.yaml" for i in resource_paths]

        for resource_type in resource_types:
            with (config_obj.get("STATIC") / f"{resource_type}.json").open(encoding="utf-8") as f:
                all_resources.update(json.load(f))
        with resource_text_file.open(encoding="utf-8") as f:
            resource_texts.update(json.load(f))
        with collections_file.open(encoding="utf-8") as f:
            collections_data = json.load(f)
            collection_mappings = {k: v.get("resources", []) for k, v in collections_data.items()}

    # Process YAML file(s) and update all_resources, collection_mappings, and resource_texts
    for filepath in filepaths:
        resource_id, resource_dict = process_yaml_file(
            filepath,
            resource_texts,
            collection_mappings,
            resource_schema,
            localizations,
            debug=debug,
            offline=offline,
            validate=validate,
        )
        if not resource_dict:
            # Resource dict is emtpty: file was deleted and should be removed from the data
            all_resources.pop(resource_id, None)
        else:
            all_resources[resource_id] = resource_dict

    # Sort alphabetically by key
    all_resources = dict(sorted(all_resources.items()))

    # Get collections data from all_resources and update collections with sizes and resource lists
    collections_data = {k: v for k, v in all_resources.items() if v.get("collection")}
    update_collections(collection_mappings, collections_data, all_resources)
    write_json(collections_file, collections_data)

    # Dump resource texts as json
    write_json(resource_text_file, resource_texts)

    # Set has_description for every resource and save as json. If resource_paths is set, only update that resource type.
    if resource_paths:
        resource_types = {Path(i).parts[0] for i in resource_paths}
    for resource_type in resource_types:
        res_json = {k: v for k, v in all_resources.items() if v.get("type", "") == resource_type}
        set_description_bool(res_json, resource_texts)
        write_json(config_obj.get("STATIC") / f"{resource_type}.json", res_json)

    if len(resource_paths) == 1:
        logger.info("Updated resource '%s'", resource_paths[0])
    elif len(resource_paths) > 1:
        logger.info("Updated resources: %s", ", ".join(resource_paths))
    else:
        logger.info("Updated all resources")


def process_yaml_file(
    filepath: Path,
    resource_texts: defaultdict,
    collection_mappings: dict,
    resource_schema: dict,
    localizations: dict,
    debug: bool = False,
    offline: bool = False,
    validate: bool = False,
) -> tuple[str, dict]:
    """Process a single YAML file and extract/process resource information.

    Update collection_mappings, and resource_texts.

    Args:
        filepath: Path to the YAML file.
        resource_texts: Dictionary to store resource texts.
        collection_mappings: Mapping from collection IDs to a list of resource IDs {collection_id: [resource_id, ...]}
        resource_schema: JSON schema for validation.
        localizations: Dictionary of localizations.
        debug: Print debug info.
        offline: Skip getting file info for downloadables.
        validate: Validate metadata using schema.

    Returns:
        The ID of the resource and the processed resource data.
    """
    fileid = filepath.stem

    # If file does not exist, remove resource from resource_texts and collection_mappings and return empty dict
    if not filepath.exists():
        resource_texts.pop(fileid, None)

        # Remove from collection_mappings in case this file is a collection
        # If this resource is part of a collection it will be removed automatically by update_collections() later.
        collection_mappings.pop(fileid, None)

        logger.info("Removed resource '%s'", filepath)
        return fileid, {}

    try:
        add_resource = True
        processed_resource = {}
        if debug:
            logger.debug("Processing '%s'", filepath)
        with filepath.open(encoding="utf-8") as f:
            res = yaml.safe_load(f)

            res_type = res.get("type")
            # Validate YAML
            if validate and resource_schema is not None:
                try:
                    jsonschema.validate(instance=res, schema=resource_schema)
                except jsonschema.exceptions.ValidationError as e:
                    logger.error("Validation error for '%s': %s", fileid, e.message)
                    add_resource = False
                except Exception:
                    logger.exception("Something went wrong when validating for '%s'", fileid)
                    add_resource = False

            if add_resource:
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
                        res[loc_name] = {"eng": key_eng, "swe": loc.get(key_eng, "")}

                if not offline:
                    # Add file info for downloadables
                    for d in res.get("downloads", []):
                        url = d.get("url")
                        if url and "size" not in d and "last-modified" not in d:
                            size, date = get_download_metadata(url, fileid, res_type)
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

    return fileid, processed_resource


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
        logger.exception("Failed to get schema '%s'", filepath)
        schema = None

    return schema


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
            logger.error("Could not find downloadable for '%s' '%s': %s", res_type, name, url)
    except Exception:
        logger.exception("Could not get downloadable '%s': %s", name, url)
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

    main(
        resource_paths=args.resource_path.split(",") if args.resource_path else None,
        debug=args.debug,
        offline=args.offline,
        validate=args.validate,
        config_obj=config_dict,
    )
