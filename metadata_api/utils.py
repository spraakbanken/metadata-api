"""Util functions used by the metadata API."""

from __future__ import annotations

import datetime
import json
from pathlib import Path
from typing import Any

from flask import Response, current_app, jsonify


def get_single_resource(
    resource_id: str,
    corpora: dict[str, Any],
    lexicons: dict[str, Any],
    models: dict[str, Any],
    analyses: dict[str, Any],
    utilities: dict[str, Any],
) -> Any:
    """Get resource from resource dictionaries and add resource text (if available).

    Args:
        resource_id: The ID of the resource.
        corpora: Dictionary of corpora resources.
        lexicons: Dictionary of lexicon resources.
        models: Dictionary of model resources.
        analyses: Dictionary of analysis resources.
        utilities: Dictionary of utility resources.

    Returns:
        JSON response containing the resource.
    """
    resource_texts = load_json(current_app.config.get("RESOURCE_TEXTS_FILE"), prefix="res_desc")
    long_description = resource_texts.get(resource_id, {})

    resource = {}
    if corpora.get(resource_id):
        resource = corpora[resource_id]
    elif lexicons.get(resource_id):
        resource = lexicons[resource_id]
    elif models.get(resource_id):
        resource = models[resource_id]
    elif analyses.get(resource_id):
        resource = analyses[resource_id]
    elif utilities.get(resource_id):
        resource = utilities[resource_id]

    if resource and long_description:
        resource["description"] = long_description

    return jsonify(resource)


def load_resources() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Load corpora, lexicons and models.

    Returns:
        Tuple containing dictionaries of corpora, lexicons, models, analyses, and utilities.
    """
    corpora = load_json(current_app.config.get("CORPORA_FILE"))
    lexicons = load_json(current_app.config.get("LEXICONS_FILE"))
    models = load_json(current_app.config.get("MODELS_FILE"))
    analyses = load_json(current_app.config.get("ANALYSES_FILE"))
    utilities = load_json(current_app.config.get("UTILITIES_FILE"))
    return corpora, lexicons, models, analyses, utilities


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
    print("Reading json", jsonfile)
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


def get_resource_type(rtype: str, resource_file: str) -> Response:
    """Get list of resources of one resource type.

    Args:
        rtype: The type of resource.
        resource_file: The resource file to load.

    Returns:
        JSON response containing the resource type and list of resources.
    """
    resource_type = load_json(current_app.config.get(resource_file))
    data = dict_to_list(resource_type)

    return jsonify({"resource_type": rtype, "hits": len(data), "resources": data})


def get_bibtex(
    resource_id: str,
    corpora: dict[str, Any],
    lexicons: dict[str, Any],
    models: dict[str, Any],
    analyses: dict[str, Any],
    utilities: dict[str, Any],
) -> str:
    """Get BibTeX entry for a resource.

    Args:
        resource_id: The ID of the resource.
        corpora: Dictionary of corpora resources.
        lexicons: Dictionary of lexicon resources.
        models: Dictionary of model resources.
        analyses: Dictionary of analysis resources.
        utilities: Dictionary of utility resources.

    Returns:
        BibTeX entry as a string.
    """
    bibtex = ""

    if corpora.get(resource_id):
        resource = corpora[resource_id]
        if resource:
            bibtex = create_bibtex(resource)
    elif lexicons.get(resource_id):
        resource = lexicons[resource_id]
        if resource:
            bibtex = create_bibtex(resource)
    elif models.get(resource_id):
        resource = models[resource_id]
        if resource:
            bibtex = create_bibtex(resource)
    elif analyses.get(resource_id):
        resource = analyses[resource_id]
        if resource:
            bibtex = create_bibtex(resource)
    elif utilities.get(resource_id):
        resource = utilities[resource_id]
        if resource:
            bibtex = create_bibtex(resource)

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
            "@misc{"
            + f_id
            + ",\n"
            + "  doi =  {"
            + f_doi
            + "},\n"
            + "  url = {"
            + f_url
            + f_id
            + "},\n"
            + "  author = {"
            + f_author
            + "},\n"
            + "  keywords = {"
            + f_keywords
            + "},\n"
            + "  language = {"
            + f_language
            + "},\n"
            + "  title = {"
            + f_title
            + "},\n"
            + "  publisher = {Språkbanken Text},\n"
            + "  year = {"
            + f_year
            + "}\n"
            + "}"
        )

    except Exception as e:
        return "Error:" + str(e)
