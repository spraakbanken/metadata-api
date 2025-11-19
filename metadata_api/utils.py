"""Util functions used by the metadata API."""

from __future__ import annotations

import datetime
import json
import logging
import tomllib
from pathlib import Path
from typing import TYPE_CHECKING, Any

import requests

if TYPE_CHECKING:
    from pymemcache.client.base import Client

logger = logging.getLogger(__name__)


def load_json(
    jsonfile: str, prefix: str = "", cache_client: Client | None = None
) -> dict[str, Any]:
    """Load data from cache if available, otherwise load from JSON file.

    Args:
        jsonfile: The JSON file to load.
        prefix: The prefix to add to keys.
        cache_client: Memcache client to use.

    Returns:
        Dictionary containing the loaded data.
    """
    if not cache_client:
        logger.warning("No memcache client available.")
        return read_static_json(jsonfile)

    # Populate cache if it's empty
    data = cache_client.get(add_prefix(jsonfile, prefix))
    if not data:
        logger.debug("Data for '%s' not found in cache. Reloading.", add_prefix(jsonfile, prefix))
        all_data = read_static_json(jsonfile)
        cache_client.set(add_prefix(jsonfile, prefix), list(all_data.keys()))
        for k, v in all_data.items():
            cache_client.set(add_prefix(k, prefix), v)
    else:
        all_data = {}
        for k in data:
            all_data[k] = cache_client.get(add_prefix(k, prefix))

    return all_data


def get_single_resource(resource_id: str, resources_dict: dict[str, Any]) -> dict[str, Any]:
    """Get resource from resource dictionaries and add long resource description if available.

    Args:
        resource_id: The ID of the resource.
        resources_dict: Dictionary of resources.

    Returns:
        Dictionary containing the resource.
    """
    from flask import current_app  # noqa: PLC0415

    resource_texts = load_json(
        current_app.config["RESOURCE_TEXTS_FILE"],
        prefix="res_descr",
        cache_client=current_app.config.get("cache_client", None),
    )
    long_description = resource_texts.get(resource_id, {})

    resource = {}
    for resource_dict in resources_dict.values():
        if resource_id in resource_dict:
            resource = resource_dict[resource_id]
            break

    if resource and long_description:
        resource["description"] = long_description

    return resource


def load_resources(
    resource_mapping: dict[str, str], cache_client: Client | None = None
) -> dict[str, Any]:
    """Load all resource types from JSON from cache or files.

    Args:
        resource_mapping: Mapping of resource types to their corresponding JSON files.
        cache_client: Memcache client to use.

    Returns:
        Dictionary containing resource dictionaries.
    """
    resources = {}
    for res_type, res_file in resource_mapping.items():
        resources[res_type] = load_json(res_file, cache_client=cache_client)
    return resources


def read_static_json(jsonfile: str) -> dict[str, Any]:
    """Load json file from static folder and return as object.

    Args:
        jsonfile: The JSON file to read.

    Returns:
        Dictionary containing the JSON data.
    """
    from flask import current_app  # noqa: PLC0415
    logger.info("Reading json %s", jsonfile)
    try:
        file_path = Path(current_app.config["STATIC"]) / jsonfile
        with file_path.open("r") as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error("File not found: %s", file_path)
        return {}
    except json.JSONDecodeError:
        logger.error("Error reading JSON file: %s", file_path)
        return {}


def add_prefix(key: str, prefix: str) -> str:
    """Add prefix to key.

    Args:
        key: The key to add a prefix to.
        prefix: The prefix to add.

    Returns:
        The key with the prefix added.
    """
    if prefix:
        key = f"{prefix}_{key}"
    return key


def dict_to_list(input_obj: dict[str, Any]) -> list:
    """Convert resource dict into list.

    Args:
        input_obj: The dictionary to convert.

    Returns:
        List of dictionary values.
    """
    # return sorted(input.values(), key=lambda x: locale.strxfrm(x.get("name_sv")))
    return list(input_obj.values())


def get_resource_type(resource_type: str) -> dict[str, Any]:
    """Get list of resources of one type.

    Args:
        resource_type: The type of resources to list.

    Returns:
        Dictionary containing the list of resources of the specified type.
    """
    from flask import current_app  # noqa: PLC0415

    filtered_resources = load_json(
        current_app.config["RESOURCES"].get(resource_type, {}),
        cache_client=current_app.config.get("cache_client", None),
    )
    data = dict_to_list(filtered_resources)

    return {"resource_type": resource_type, "hits": len(data), "resources": data}


def get_bibtex(resource_id: str, resources_dict: dict[str, Any]) -> str:
    """Get BibTeX entry for a resource.

    Args:
        resource_id: The ID of the resource.
        resources_dict: Dictionary of resources.

    Returns:
        BibTeX entry as a string.
    """
    for resource_type in resources_dict.values():
        if resource_id in resource_type:
            return create_bibtex(resource_type[resource_id])
    return "Error: Resource not found"


def create_bibtex(resource: dict[str, Any]) -> str:
    """Create bibtex record for resource.

    Args:
        resource: The resource dictionary.

    Returns:
        BibTeX entry as a string.
    """
    try:
        f_doi = resource.get("doi", "")
        f_id = resource.get("id", "")  # id/slug/maskinnamn
        f_creators = resource.get("creators", [])  # creators, "Skapad av"
        f_author = " and ".join(f_creators) if len(f_creators) > 0 else "Språkbanken Text"
        f_words = resource.get("keywords", [])
        f_words.insert(0, "Language Technology (Computational Linguistics)")
        f_keywords = ", ".join(f_words)
        f_languages = resource.get("languages", [])
        if len(f_languages) > 0:
            f_language = f_languages[0].get("code", "")
            for item in f_languages[1:]:
                f_language += ", " + item.get("code", "")
        else:
            f_language = ""
        f_title = resource["name"].get("eng", "")
        if f_title:
            f_title = resource["name"].get("swe", "")
        # Get year, fallback to current year
        f_year = str(datetime.datetime.now().date().year)
        f_updated = resource.get("updated", "")
        if f_updated:
            f_year = f_updated[:4]
        else:
            f_created = resource.get("created", "")
            if f_created:
                f_year = f_created[:4]

        # Target URL
        match resource["type"]:
            case "analysis" | "utility":
                f_url = "https://spraakbanken.gu.se/analyser/"
            case "corpus" | "lexicon" | "model":
                f_url = "https://spraakbanken.gu.se/resurser/"
            case _:
                # Fallback
                f_url = "https://spraakbanken.gu.se/resurser/"

        # Build bibtex string
        return (
            f"@misc{{{f_id},\n"
            f"  doi = {{{f_doi}}},\n"
            f"  url = {{{f_url}{f_id}}},\n"
            f"  author = {{{f_author}}},\n"
            f"  keywords = {{{f_keywords}}},\n"
            f"  language = {{{f_language}}},\n"
            f"  title = {{{f_title}}},\n"
            f"  publisher = {{Språkbanken Text}},\n"
            f"  year = {{{f_year}}}\n"
            "}"
        )

    except Exception as e:
        logger.exception("Error creating BibTeX entry")
        return "Error:" + str(e)


def send_to_slack(message: str, slack_webhook: str) -> None:
    """Send message to Slack.

    Args:
        message: The message to send.
        slack_webhook: The Slack webhook URL.
    """
    if not slack_webhook:
        logger.warning("No Slack webhook configured.")
        return
    try:
        requests.post(slack_webhook, json={"text": message})
    except Exception as e:
        logger.error("Error sending message to Slack, %s", e)
        logger.exception("Error sending message to Slack")


def get_version_from_pyproject(path: Path = Path("pyproject.toml")) -> str:
    """Get the version of the project from the pyproject.toml file.

    Args:
        path: Path to the pyproject.toml file.
    """
    # print absolute path
    path = path.resolve()
    if not path.exists() or not path.is_file():
        logger.error("Could not find pyproject.toml file at %s", path)
        raise FileNotFoundError(f"Could not find pyproject.toml file at {path}")
    with path.open("rb") as f:
        data = tomllib.load(f)
    return data["project"]["version"]
