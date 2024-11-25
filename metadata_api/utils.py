"""Util functions used by the metadata API."""

import datetime
import json
from pathlib import Path

from flask import current_app, jsonify


def get_single_resource(resource_id, corpora, lexicons, models, analyses, utilities):
    """Get resource from resource dictionaries and add resource text (if available)."""
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


def load_resources():
    """Load corpora, lexicons and models."""
    corpora = load_json(current_app.config.get("CORPORA_FILE"))
    lexicons = load_json(current_app.config.get("LEXICONS_FILE"))
    models = load_json(current_app.config.get("MODELS_FILE"))
    analyses = load_json(current_app.config.get("ANALYSES_FILE"))
    utilities = load_json(current_app.config.get("UTILITIES_FILE"))
    return corpora, lexicons, models, analyses, utilities


def load_json(jsonfile, prefix=""):
    """Load data from cache."""
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


def read_static_json(jsonfile):
    """Load json file from static folder and return as object."""
    print("Reading json", jsonfile)  # noqa: T201
    file_path = Path(current_app.config.get("STATIC")) / jsonfile
    with file_path.open("r") as f:
        return json.load(f)


def add_prefix(key, prefix):
    """Add prefix to key."""
    if prefix:
        key = f"{prefix}_{key}"
    return key


def dict_to_list(input_obj):
    """Convert resource dict into list."""
    # return sorted(input.values(), key=lambda x: locale.strxfrm(x.get("name_sv")))
    return list(input_obj.values())


def get_resource_type(rtype, resource_file):
    """Get list of resources of one resource type."""
    resource_type = load_json(current_app.config.get(resource_file))
    data = dict_to_list(resource_type)

    return jsonify({
        "resource_type": rtype,
        "hits": len(data),
        "resources": data
    })


def get_bibtex(resource_type, resource_id):
    
    bibtex = ""

    match resource_type:
        case "corpus":
            corpora = load_json(current_app.config.get("CORPORA_FILE"))
            if corpora.get(resource_id):
                resource = corpora[resource_id]
                if resource:
                    bibtex = create_bibtex(resource)
        case "lexicon":
            lexicons = load_json(current_app.config.get("LEXICONS_FILE"))
            if lexicons.get(resource_id):
                resource = lexicons[resource_id]
                if resource:
                    bibtex = create_bibtex(resource)
        case "model":
            models = load_json(current_app.config.get("MODELS_FILE"))
            if models.get(resource_id):
                resource = models[resource_id]
                if resource:
                    bibtex = create_bibtex(resource)
        case "analysis":
            analyses = load_json(current_app.config.get("ANALYSES_FILE"))
            if analyses.get(resource_id):
                resource = analyses[resource_id]
                if resource:
                    bibtex = create_bibtex(resource)
        case "utility":
            utilities = load_json(current_app.config.get("UTILITIES_FILE"))
            if utilities.get(resource_id):
                resource = utilities[resource_id]
                if resource:
                    bibtex = create_bibtex(resource)

    return bibtex


def create_bibtex(resource):
    """Create bibtex record for resource"""

    # DOI
    f_doi = resource["doi"]
    return f_doi
