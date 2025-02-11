"""Util functions used by the metadata API."""

from __future__ import annotations

import datetime
import json
import logging
from pathlib import Path
from typing import Any

from flask import Response, current_app, jsonify

logger = logging.getLogger(__name__)


def get_single_resource(resource_id: str, resources_dict: dict[str, Any]) -> Response:
    """Get resource from resource dictionaries and add long resource description if available.

    Args:
        resource_id: The ID of the resource.
        resources_dict: Dictionary of resources.

    Returns:
        JSON response containing the resource.
    """
    resource_texts = load_json(current_app.config.get("RESOURCE_TEXTS_FILE"), prefix="res_desc")
    long_description = resource_texts.get(resource_id, {})

    resource = {}
    for resource_dict in resources_dict.values():
        if resource_id in resource_dict:
            resource = resource_dict[resource_id]
            break

    if resource and long_description:
        resource["description"] = long_description

    return jsonify(resource)


def load_resources() -> dict[str, dict[str, Any]]:
    """Load all resource types from JSON from cache or files.

    Returns:
        Dictionary containing resource dictionaries.
    """
    resources = {}
    for res_type, res_file in current_app.config.get("RESOURCES").items():
        resources[res_type] = load_json(res_file)
    return resources


def load_json(jsonfile: str, prefix: str = "") -> dict[str, Any]:
    """Load data from cache.

    Args:
        jsonfile: The JSON file to load.
        prefix: The prefix to add to keys.

    Returns:
        Dictionary containing the loaded data.
    """
    if current_app.config.get("NO_CACHE"):
        return read_static_json(jsonfile)

    mc = current_app.config.get("cache_client")
    if not mc:
        logger.warning("No memcache client available.")
        return read_static_json(jsonfile)

    # Repopulate cache if it's empty
    data = mc.get(add_prefix(jsonfile, prefix))
    if not data:
        all_data = read_static_json(jsonfile)
        mc.set(add_prefix(jsonfile, prefix), list(all_data.keys()))
        for k, v in all_data.items():
            mc.set(add_prefix(k, prefix), v)
    else:
        all_data = {}
        for k in data:
            all_data[k] = mc.get(add_prefix(k, prefix))

    return all_data


def read_static_json(jsonfile: str) -> dict[str, Any]:
    """Load json file from static folder and return as object.

    Args:
        jsonfile: The JSON file to read.

    Returns:
        Dictionary containing the JSON data.
    """
    logger.info("Reading json %s", jsonfile)
    file_path = Path(current_app.config.get("STATIC")) / jsonfile
    with file_path.open("r") as f:
        return json.load(f)


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


def get_resource_type(resource_type: str) -> Response:
    """Get list of resources of one type.

    Args:
        resource_type: The type of resources to list.

    Returns:
        JSON response containing the list of resources of the specified type.
    """
    filtered_resources = load_json(current_app.config.get("RESOURCES").get(resource_type, {}))
    data = dict_to_list(filtered_resources)

    return jsonify({"resource_type": resource_type, "hits": len(data), "resources": data})


def get_bibtex(resource_id: str, resources_dict: dict[str, Any]) -> str:
    """Get BibTeX entry for a resource.

    Args:
        resource_id: The ID of the resource.
        resources_dict: Dictionary of resources.

    Returns:
        BibTeX entry as a string.
    """
    bibtex = ""
    for resource_type in resources_dict.values():
        if resource_id in resource_type:
            bibtex = create_bibtex(resource_type[resource_id])
    return bibtex


def create_bibtex(resource: dict[str, Any]) -> str:
    """Create bibtex record for resource.

    Args:
        resource: The resource dictionary.

    Returns:
        BibTeX entry as a string.
    """
    try:
        # DOI
        f_doi = resource.get("doi", "")
        # id/slug/maskinnamn
        f_id = resource.get("id", "")
        # creators, "Skapad av"
        f_creators = resource.get("creators", [])
        f_author = " and ".join(f_creators) if len(f_creators) > 0 else "Språkbanken Text"
        # keywords
        f_words = resource.get("keywords", [])
        f_words.insert(0, "Language Technology (Computational Linguistics)")
        # f_keywords = "Language Technology (Computational Linguistics)"
        f_keywords = ", ".join(f_words)
        # languages
        f_languages = resource.get("languages", [])
        if len(f_languages) > 0:
            f_language = f_languages[0].get("code", "")
            for item in f_languages[1:]:
                f_language += ", " + item.get("code", "")
        else:
            f_language = ""
        # name, title
        f_title = resource["name"].get("eng", "")
        if f_title:
            f_title = resource["name"].get("swe", "")
        # year, fallback to current year
        f_year = str(datetime.datetime.now().date().year)
        f_updated = resource.get("updated", "")
        if f_updated:
            f_year = f_updated[:4]
        else:
            f_created = resource.get("created", "")
            if f_created:
                f_year = f_created[:4]
        # target URL
        match resource["type"]:
            case "analysis" | "utility":
                f_url = "https://spraakbanken.gu.se/analyser/"
            case "corpus" | "lexicon" | "model":
                f_url = "https://spraakbanken.gu.se/resurser/"
            case _:
                # fallback
                f_url = "https://spraakbanken.gu.se/resurser/"

        # build bibtex string
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
        return "Error:" + str(e)
