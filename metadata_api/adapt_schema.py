"""Adapt JSON schema to the resource data that is output by the API."""


# Changes to be applied to the JSON schema
SCHEMA_CHANGES = {
    # Properties to add or update
    "update_properties": {
        "id": {
            "description": "Unique identifier for the resource",
            "type": "string",
            "pattern": "^[a-z0-9_-]+$"
        },
        "has_description": {
            "description": "If set to true, the resource has a description",
            "type": "boolean",
            "default": False
        },
        "downloads": {
            "items": {
                "properties": {
                    "size": {
                        "type": "integer",
                        "description": "File size in bytes"
                    },
                    "last-modified": {
                        "type": "string",
                        "description": "Last modified date"
                    }
                }
            }
        },
    },

    # Required properties to add
    "update_required": ["id"],

    # Conditional properties to update. The key can be one of the following:
    #   - a string in an enum inside and if condition
    #   - the name of a property inside an "if" condition
    # The value is a dictionary with the properties to update inside the "then" part of the condition.
    "update_conditionals": {
        "analysis": {
            "task": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "eng": {
                        "description": "Task name in English",
                        "type": "string"
                    },
                    "swe": {
                        "description": "Task name in Swedish",
                        "type": "string"
                    }
                }
            },
            "analysis_unit": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "eng": {
                        "description": "Unit name in English",
                        "type": "string"
                    },
                    "swe": {
                        "description": "Unit name in Swedish",
                        "type": "string"
                    }
                }
            }
        },
        "collection": {
            "size": {
                "description": "Size information about the collection",
                "type": "object",
                "additionalProperties": True,
                "properties": {
                    "resources": {
                        "description": "Number of resources in the collection",
                        "type": "integer"
                    }
                }
            }
        }
    },
}


def adapt_schema(schema: dict) -> dict:
    """Adapt schema to the resource data that is output by the API.

    Args:
        schema: JSON schema.

    Returns:
        Adapted JSON schema.
    """
    # Update schema properties
    for key, value in SCHEMA_CHANGES.get("update_properties", {}).items():
        if key in schema["properties"]:
            schema["properties"][key] = _deep_update(schema["properties"][key], value)
        else:
            schema["properties"][key] = value

    # Update required properties
    schema["required"].extend(SCHEMA_CHANGES.get("update_required", []))

    # Update conditional properties
    for key, value in SCHEMA_CHANGES["update_conditionals"].items():
        schema_part = _search_schema(schema, key)
        if schema_part:
            schema_part["then"]["properties"] = _deep_update(schema_part["then"]["properties"], value)

    return schema


def _search_schema(schema_part: dict | list | None, search_str: str) -> dict:
    """Search recursively for a specific structure in the schema.

    This function traverses a given schema, which can be a dictionary or a list,
    to find a specific key-value pair within the "properties" of an "if" condition.

    Args:
        schema_part: The part of the schema to search in, can be a dictionary or a list.
        search_str: The key or value to search for in the schema.

    Returns:
        The schema part itself if the key-value pair is found, otherwise an empty dict.
    """
    if isinstance(schema_part, dict):
        for key, value in schema_part.items():
            if key == "if" and isinstance(value, dict):
                properties = value.get("properties", {})
                enum = properties.get("type", {}).get("enum", [])
                if search_str in properties or search_str in enum:
                    return schema_part
            result = _search_schema(value, search_str)
            if result:
                return result
    elif isinstance(schema_part, list):
        for item in schema_part:
            result = _search_schema(item, search_str)
            if result:
                return result
    return {}


def _deep_update(mapping: dict, updating_mapping: dict) -> dict:
    """Recursively updates a dictionary with one or more dictionaries.

    Copied from pydantic:
    https://github.com/pydantic/pydantic/blob/fd2991fe6a73819b48c906e3c3274e8e47d0f761/pydantic/utils.py#L200

    Args:
        mapping (dict[KeyType, Any]): The original dictionary to be updated.
        updating_mapping (dict[KeyType, Any]): One or more dictionaries to update the original dictionary with.

    Returns:
        dict[KeyType, Any]: The updated dictionary.

    Example:
        original = {'a': 1, 'b': {'c': 2}}
        update1 = {'b': {'d': 3}}
        update2 = {'e': 4}
        result = _deep_update(original, update1, update2)
        # result is {'a': 1, 'b': {'c': 2, 'd': 3}, 'e': 4}
    """
    updated_mapping = mapping.copy()
    for k, v in updating_mapping.items():
        if k in updated_mapping and isinstance(updated_mapping[k], dict) and isinstance(v, dict):
            updated_mapping[k] = _deep_update(updated_mapping[k], v)
        else:
            updated_mapping[k] = v
    return updated_mapping
