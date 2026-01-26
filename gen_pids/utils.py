"""Helper functions for DMS metadata generation."""

import datetime
import logging
import re
from typing import Any

import markdown
from bs4 import BeautifulSoup

from gen_pids.settings import (
    DMS_CREATOR_NAME,
    DMS_CREATOR_ROR,
    DMS_LANG_ENG,
    DMS_LANG_MUL,
    DMS_LICENSE_OTHER,
    DMS_LICENSE_SCHEME_ID,
    DMS_LICENSE_SCHEME_URI,
    DMS_RESOURCE_TYPE_ANALYSIS,
    DMS_RESOURCE_TYPE_DATASET,
)

logger = logging.getLogger("gen_pids")


def expand_res_ref(res_refs: list[str], all_resources: dict) -> list[str]:
    """Expand a resource reference with possible wildcards and type prefix to a list of matching resource IDs.

    E.g.: "corpus/kubhist-*" -> ["kubhist-dalpilen-1850", "kubhist-dalpilen-1860", ...]

    Args:
        res_refs: A list of resource reference strings, which may contain wildcards or a type prefix (e.g. "corpus/*").
        all_resources: Dictionary of all resources {resource_id: resource_dict, ...}.
    """
    expanded_res_ids = []
    for res_ref in res_refs:
        if "/" in res_ref:
            res_type, res_id_part = res_ref.split("/", 1)
            expanded_res_ids.extend([
                res_id
                for res_id, res_data in all_resources.items()
                if res_data.get("type") == res_type and wildcard_match(res_id_part, res_id)
            ])
        if "*" in res_ref or "?" in res_ref:
            expanded_res_ids.extend([res_id for res_id in all_resources if wildcard_match(res_ref, res_id)])
        else:
            expanded_res_ids.append(res_ref)

    if res_refs != expanded_res_ids:
        logger.debug("Expanded resource references %s to %s resources", res_refs, len(expanded_res_ids))

    # Make sure all returned resource IDs exist
    return [res_id for res_id in expanded_res_ids if res_id in all_resources]


def wildcard_match(pattern: str, value: str) -> bool:
    """Match simple glob-style patterns (* and ?) against a value.

    Args:
        pattern: The pattern containing wildcards.
        value: The value to match against the pattern.

    Returns:
        Whether the value matches the pattern.
    """
    regex = re.escape(pattern)
    regex = regex.replace(r"\*", ".*").replace(r"\?", ".")
    return bool(re.fullmatch(regex, value))


def ensure_collection_entry(collections: dict, res_id: str, relation_type: str) -> None:
    """Ensure that collections dict has an entry for the given resource and relation type.

    Args:
        collections: collection mapping dictionary
        res_id: resource id
        relation_type: relation type to ensure
    """
    if res_id not in collections:
        collections[res_id] = {}
    if relation_type not in collections[res_id]:
        collections[res_id][relation_type] = []


def is_dataset(resource: dict) -> bool:
    """Return True is resource is a dataset (corpus, lexicon, model, training data), false if it is an analysis.

    Args:
        resource: a resource dict

    Returns:
        True if resource is dataset, i.e. not analysis/utility
    """
    return not (get_key_value(resource, "type") == "analysis" or get_key_value(resource, "type") == "utility")


def get_res_type_str(dataset: bool) -> str:
    """Return string describing the resource."""
    if dataset:
        return DMS_RESOURCE_TYPE_DATASET
    return DMS_RESOURCE_TYPE_ANALYSIS


def get_res_lang_code(language_list: list) -> str:
    """Translate code to ISO right version."""
    if language_list:
        if len(language_list) == 1:
            return language_list[0]
        return DMS_LANG_MUL  # language_list[0]
    return ""


def get_res_size(size_list: dict) -> str:
    """Create string of resource size info, e.g. 'sentences: 10. tokens: 1000'."""
    if not isinstance(size_list, dict):
        return ""
    return ". ".join(f"{key}: {value}" for key, value in size_list.items())


def get_res_license(item: dict) -> dict:
    """Create item for rightsList structure.

    Returns:
        rightsList item
    """
    rights = item.get("license", "")  # eg "CC BY 4.0"

    # rights_str = item["license_other"] if rights == DMS_LICENSE_OTHER else rights

    if rights == DMS_LICENSE_OTHER:  # noqa: SIM108
        rights_str = item.get("license_other", "")
    else:
        rights_str = rights

    return {
        "rights": rights_str,
        "lang": DMS_LANG_ENG,
        "schemeURI": DMS_LICENSE_SCHEME_URI,
        "rightsIdentifierScheme": DMS_LICENSE_SCHEME_ID,
        "rightsIdentifier": rights,
    }


def get_res_rights(downloads_list: list) -> list:
    """Create dict of resource rights information.

    Returns:
        list of rightsList items
    """
    result_list = []
    for item in downloads_list:
        rights = get_res_license(item)
        if rights:
            result_list.append(rights)
    # return [{"rights": rights} for rights in result_set]
    return result_list


def get_res_rights_a(license_code: str, tools_list: list, models_list: list) -> list:
    """Create dict of analysis rights information.

    Analysis licenses has three ways of specifiying license:
    - 'license': string (for code)
    - 'tools' - 'license': string (for tool)
    - 'models' - 'license': string (for model)

    Returns:
        list of rightsList items
    """
    result_list = []
    if license_code:
        rights = get_res_license({"license": license_code})
        if rights:
            result_list.append(rights)
    for item in tools_list:
        rights = get_res_license(item)
        if rights:
            result_list.append(rights)
    for item in models_list:
        rights = get_res_license(item)
        if rights:
            result_list.append(rights)

    return result_list
    # return [{"rights": rights} for rights in result_set]


def get_res_creators(res: dict) -> list:
    """Build creators structure."""
    # Creator is Språkbanken Text as default, but could be people
    creators = res.get("creators", [])
    # If creators are people
    if creators:
        dms_creators = [{"name": creator, "nameType": "Personal"} for creator in creators]
    else:
        dms_creators = [
            {
                "name": DMS_CREATOR_NAME,
                "nameType": "Organizational",
                "nameIdentifiers": [
                    {
                        "schemeURI": "https://ror.org/",
                        "nameIdentifier": DMS_CREATOR_ROR,
                        "nameIdentifierScheme": "ROR",
                    }
                ],
            }
        ]
    return dms_creators


def get_res_keywords(res: dict) -> list:
    """Build keywords structure."""
    keywords = res.get("keywords", [])
    if keywords:  # noqa: SIM108
        dms_keywords = [{"subject": keyword, "subjectScheme": "keyword"} for keyword in keywords]
    else:
        dms_keywords = []
    return dms_keywords


def get_res_dates(res: dict) -> tuple[str, str]:
    """Return 'created' and 'updated' dates as strings and check that they are valid."""
    created = get_key_value(res, "created")
    if created:
        if type(created) is str:
            created_str = created
        else:
            # Assume type is date
            created_str = datetime.datetime.strftime(created, "%Y-%m-%d") if created else ""
    else:
        created_str = ""

    updated = get_key_value(res, "updated")
    if updated:
        if type(updated) is str:
            updated_str = updated
        else:
            # Assume type is date
            updated_str = datetime.datetime.strftime(updated, "%Y-%m-%d") if updated else ""
    else:
        updated_str = ""
    return created_str, updated_str


def get_clean_string(string: str) -> str:
    """Remove HTML etc from string."""
    # value = re.sub('<[^>]+>', '', value) # remove HTML tags
    # value = re.sub(r'\n\s*\n', '\n\n', value) # remove multiple newlines
    # return re.sub(r"<.*?>", "", string)

    # Handle beginning-of-code quotes, eg ```xml
    md = re.sub(r"(^\s*```)[^\s`]+\n", r"\1", string, flags=re.MULTILINE)
    # Transform from markdown to HTML
    html = markdown.markdown(md)
    # Let BS export clean text
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text()
    # Remove multiple newlines
    return re.sub(r"\n\s*\n", "\n\n", text)


def get_key_value(dictionary: dict, key: str, key2: str | None = None) -> Any:
    """Return key value from dictionary, else empty string."""
    if key2 is None:
        value = dictionary.get(key, "")
        return value or ""
    if key in dictionary:
        value = get_key_value(dictionary[key], key2)
        return value or ""
    return ""


def get_doi_from_rid(res: dict, rid: str) -> str:
    """Return DOI belonging to a resource ID.

    Args:
        res: Resources
        rid: resource ID

    Returns:
        DOI or "" if rid not found.
    """
    if rid in res and "doi" in res[rid]:
        return res[rid]["doi"]
    return ""
