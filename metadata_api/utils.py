"""Util functions used by the metadata API."""

import json
import os

from flask import current_app, jsonify


def get_single_resource(resource_id, corpora, lexicons, models):
    """Get resource from resource dictionaries and add resource text (if available)."""
    resource_texts = load_data(current_app.config.get("RESOURCE_TEXTS_FILE"), prefix="res_desc")
    long_description = resource_texts.get(resource_id, {})

    resource = {}
    if corpora.get(resource_id):
        resource = corpora[resource_id]
    elif lexicons.get(resource_id):
        resource = lexicons[resource_id]
    elif models.get(resource_id):
        resource = models[resource_id]

    if resource and long_description:
        resource["description"] = long_description

    return jsonify(resource)


def load_data(jsonfile, prefix="", remove_keys=None):
    """Load data from cache."""
    if current_app.config.get("NO_CACHE"):
        all_data = read_static_json(jsonfile)
    else:
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
    if remove_keys:
        for val in all_data.values():
            for rk in remove_keys:
                val.pop(rk, None)
    return all_data


def read_static_json(jsonfile):
    """Load json file from static folder and return as object."""
    print("Reading json", jsonfile)
    file_path = os.path.join(current_app.config.get("STATIC"), jsonfile)
    with open(file_path, "r") as f:
        return json.load(f)


def add_prefix(key, prefix):
    """Add prefix to key."""
    if prefix:
        key = "{}_{}".format(prefix, key)
    return key


def dict_to_list(input_obj):
    """Convert resource dict into list."""
    # return sorted(input.values(), key=lambda x: locale.strxfrm(x.get("name_sv")))
    return list(input_obj.values())


def get_resource_type(rtype, resource_file):
    """Get list of resources of one resource type."""
    remove_keys = current_app.config.get("HIDE_FROM_LISTING")
    resource_type = load_data(current_app.config.get(resource_file), remove_keys=remove_keys)
    data = dict_to_list(resource_type)

    return jsonify({
        "resource_type": rtype,
        "hits": len(data),
        "resources": data
    })
