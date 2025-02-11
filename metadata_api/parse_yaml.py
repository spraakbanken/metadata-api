"""Read YAML metadata files, compile and prepare information for the API."""

from __future__ import annotations

import argparse
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

# Swedish translations for language names
SWEDISH = gettext.translation("iso639-3", pycountry.LOCALES_DIR, languages=["sv"])

# Instatiate command line arg parser
parser = argparse.ArgumentParser(description="Read YAML metadata files, compile and prepare information for the API")
parser.add_argument("--debug", action="store_true", help="Print debug info")
parser.add_argument("--offline", action="store_true", help="Skip getting file info for downloadables")
parser.add_argument("--validate", action="store_true", help="Validate metadata using schema")

logger = logging.getLogger(__name__)


# TODO: Remove when this file is no longer used as a script
class Config:
    """Configuration class to hold settings."""
    def __init__(
        self, yaml_dir: Path, schema_file: Path, resource_texts_file: Path, static_dir: Path, localizations_dir: Path
    ) -> None:
        """Initialize the configuration with the given paths.

        Args:
            yaml_dir: Path to the directory containing YAML files.
            schema_file: Path to the JSON schema file.
            resource_texts_file: Path to the resource texts file.
            static_dir: Path to the static directory.
            localizations_dir: Path to the localizations directory.
        """
        self.YAML_DIR = yaml_dir
        self.SCHEMA_FILE = schema_file
        self.RESOURCE_TEXTS_FILE = resource_texts_file
        self.STATIC = static_dir
        self.LOCALIZATIONS_DIR = localizations_dir


def main(
    resource_types: list[str] | None = None,
    file_path: str | None = None,
    debug: bool = False,
    offline: bool = False,
    validate: bool = False,
    config: Config | None = None,
) -> None:
    """Read YAML metadata files, compile and prepare information for the API (main wrapper).

    Args:
        resource_types: List of resource types to process.
        file_path: Specific file path to process.
        debug: Print debug info.
        offline: Skip getting file info for downloadables.
        validate: Validate metadata using schema.
        config: Configuration object.
    """
    if resource_types is None:
        resource_types = ["lexicon", "corpus", "model", "analysis", "utility"]
    resource_ids = []
    all_resources = {}
    resource_texts = defaultdict(dict)
    collection_mappings = {}
    if config is None:
        raise ValueError("Configuration object is required")
    localizations = get_localizations(config)

    if validate:
        resource_schema = get_schema(Path(config.SCHEMA_FILE))
        # YAML safe_load() - handle dates as strings
        yaml.constructor.SafeConstructor.yaml_constructors["tag:yaml.org,2002:timestamp"] = (
            yaml.constructor.SafeConstructor.yaml_constructors["tag:yaml.org,2002:str"]
        )
    else:
        resource_schema = None

    # TODO: Add support for processing a single file and updating the files accordingly
    if file_path:
        pass

    yaml_dir = Path(config.YAML_DIR)
    file_paths = sorted(yaml_dir.glob("**/*.yaml"))

    for filepath in file_paths:
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
    write_json(Path(config.RESOURCE_TEXTS_FILE), resource_texts)

    # Set has_description for every resource and save as json
    for resource_type in resource_types:
        res_json = {k: v for k, v in all_resources.items() if v.get("type", "") == resource_type}
        set_description_bool(res_json, resource_texts)
        write_json(config.STATIC / f"{resource_type}.json", res_json)
    write_json(config.STATIC / "collection.json", collection_json)


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
            logger.debug("Processing '%s'", filepath)
        with filepath.open(encoding="utf-8") as f:
            res = yaml.safe_load(f)
            fileid = filepath.stem

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

    except Exception:
        logger.exception("Failed to process '%s'", filepath)

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


def get_localizations(config: Config) -> dict:
    """Read localizations from YAML files.

    Args:
        config: Configuration object.

    Returns:
        Localizations as a dictionary.
    """
    localizations = {}
    for filepath in Path(config.LOCALIZATIONS_DIR).glob("**/*.yaml"):
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


if __name__ == "__main__":
    # Configure logging
    LOG_FORMAT = "%(levelname)s - %(message)s"
    logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)

    args = parser.parse_args()

    config_obj = Config(
        yaml_dir=Path("../metadata/yaml"),
        schema_file=Path("../metadata/schema/metadata.json"),
        resource_texts_file=Path("static/resource-texts.json"),
        static_dir=Path("static"),
        localizations_dir=Path("../metadata/localizations"),
    )
    main(debug=args.debug, offline=args.offline, validate=args.validate, config=config_obj)
