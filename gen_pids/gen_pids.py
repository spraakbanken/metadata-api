"""Read YAML metadata files, set DOIs for resources that miss one."""

import argparse
import datetime
import logging
import netrc
import re
import sys
import time
import traceback
from pathlib import Path
from typing import Any

import markdown
import requests
import yaml
from bs4 import BeautifulSoup
from requests.auth import HTTPBasicAuth

YAML_DIR = Path("../metadata/yaml")
DOI_KEY = "doi"
DMS_URL = "https://api.datacite.org/dois"
DMS_HEADERS = {
    "content-type": "application/json",
    "User-agent": "GenPids/1.0 (https://spraakbanken.gu.se; mailto:sb-webb@svenska.gu.se)",
}
DMS_PREFIX = "10.23695"
DMS_REPOID = "SND.SPRKB"
DMS_CREATOR_NAME = "Språkbanken Text"
DMS_CREATOR_ROR = "https://ror.org/03xfh2n14"
DMS_TARGET_RESOURCE_PREFIX = "https://spraakbanken.gu.se/resurser/"
DMS_TARGET_ANALYSIS_PREFIX = "https://spraakbanken.gu.se/analyser/"
DMS_RESOURCE_TYPE_DATASET = "Dataset"
DMS_RESOURCE_TYPE_ANALYSIS = "Workflow"
DMS_RESOURCE_TYPE_COLLECTION = "Collection"
DMS_SLUG = "slug"  # Språkbanken Texts resource ID ("slug") type
DMS_HANDLE = "handle"
DMS_LANG_ENG = "en"
DMS_LANG_SWE = "sv"
DMS_LANG_MUL = "mul"
DMS_TITLE_EXAMPLE_SWE = "Exempel (in English)"
DMS_TITLE_EXAMPLE_ENG = "Example"
DMS_LICENSE_SCHEME_URI = "https://spdx.org/licenses/"
DMS_LICENSE_SCHEME_ID = "SPDX"
DMS_LICENSE_OTHER = "LicenseRef-Other"

DMS_RELATION_TYPE_ISPARTOF = "IsPartOf"
DMS_RELATION_TYPE_HASPART = "HasPart"
DMS_RELATION_TYPE_ISOBSOLETEDBY = "IsObsoletedBy"
DMS_RELATION_TYPE_OBSOLETES = "Obsoletes"

RESPONSE_OK = 200
RESPONSE_CREATED = 201
DATACITE_RATE_LIMIT = 298
DATACITE_RATE_LIMIT_TIMEOUT = 60 * 5

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(name)s/%(funcName)s: %(levelname)s - %(message)s")
logger = logging.getLogger("gen_pids")

# Get DataCite authenticators from netrc file
try:
    auth = netrc.netrc().authenticators("datacite.org")
    if auth is None:
        raise ValueError("No authenticators found for datacite.org in netrc file.")
    DMS_AUTH_USER, DMS_AUTH_ACCOUNT, DMS_AUTH_PASSWORD = auth
except Exception:
    logger.critical("Failed to retrieve DataCite authenticators from netrc. Exiting.")
    logger.critical(traceback.format_exc())
    # TODO: when rewriting the API (https://github.com/spraakbanken/metadata-api/issues/26) this file might no longer be
    # a script but instead a module which is imported. Then we don't want to exit the whole program here, but rather
    # raise an exception that can be caught by the caller.
    sys.exit()

# Instantiate command line arg parser
parser = argparse.ArgumentParser(
    description="Read YAML metadata files, create DOIs for those that are missing it, "
    "create and update Datacite metadata."
)
parser.add_argument("--debug", "-d", action="store_true", help="Print debug info")
parser.add_argument(
    "--test", "-t", action="store_true", help="Test - don't write back YAML and don't call Datacite to create DOI"
)
parser.add_argument("--noupdate", "-n", action="store_true", help="Do not update Datacite metadata, only create DOIs")
parser.add_argument("--analyses", "-a", action="store_true", help="Create Datacite metadata for analyses")
parser.add_argument("--update", "-u", action="store_true", help="Force update of all metadata at Datacite")
parser.add_argument("-f", action="store", dest="param_file", type=str)


def main(
    param_debug: bool = False,
    param_test: bool = False,
    param_noupdate: bool = False,
    param_analyses: bool = False,
    param_update: bool = False,
    param_file: str | None = None,
) -> None:
    """Read YAML metadata files, compile and prepare information for the API (main wrapper).

    Args:
        param_debug: Print messages about what it is doing.
        param_test: Do not modify YAML (but DMS is still created/updated).
        param_noupdate: Do not update Datacite metadata, only create DOIs for resources without
        param_analyses: Also process analyses/utilities and create DOI:s for them
        param_update: Force update of all metadata at Datacite. Overridden by param_noupdate.
        param_file: Pass a filename that will be handled -- else all files are read.
                            Filename built from YAML_DIR.

    1. Get all resources YAML metadata
    2. Assign DOIs
        if metadata has no DOI
            look up in DataCite repos (using slug/name) if it exists anyway, and get DOI
            put metadata into Datacite repos and get a DOI
            add DOI to YAML metadata file
        if it has DOI, update ALL information depending on dates
    3. Map collections and successors into relatedIdentifiers
        update Datacite repos
    """
    if param_debug:
        logger.setLevel(logging.DEBUG)

    # 1. Get all resources

    resources = {}
    files_yaml = {}

    logger.debug("Reading resources from YAML.")

    if param_file is None:
        # Find all resources YAML files recursively
        for filepath in sorted(YAML_DIR.glob("**/*.yaml")):
            try:
                res_id = filepath.stem
                files_yaml[res_id] = filepath
                with filepath.open(encoding="utf-8") as file_yaml:
                    res = yaml.safe_load(file_yaml)
                    if not get_key_value(res, "unlisted") and (param_analyses or is_dataset(res)):
                        resources[res_id] = res

            except Exception:
                logger.exception("Error when opening/reading YAML file '%s'", filepath)
                # sys.exit()
    else:
        filepath = YAML_DIR / param_file
        short_filepath = filepath.relative_to(YAML_DIR).with_suffix("")
        logger.debug("Reading from '%s'", short_filepath)

        # Get resource from yaml
        try:
            res_id = filepath.stem
            files_yaml[res_id] = filepath
            with filepath.open(encoding="utf-8") as file_yaml:
                res = yaml.safe_load(file_yaml)
                if not get_key_value(res, "unlisted") and (param_analyses or is_dataset(res)):
                    resources[res_id] = res

        except Exception:
            logger.exception("Error when opening/reading YAML file '%s'. Exiting.", filepath)
            sys.exit()

    datacite_calls = 0

    # 2. Assign DOIs
    logger.debug("Assign DOIs to %d resources.", len(resources))
    for res_id, res in resources.items():
        short_filepath = files_yaml[res_id].relative_to(YAML_DIR).with_suffix("")
        if datacite_calls > DATACITE_RATE_LIMIT:
            logger.debug("Rate limit reached, Sleeping...")
            time.sleep(DATACITE_RATE_LIMIT_TIMEOUT)
            datacite_calls = 0
        try:
            logger.debug("Working on '%s'", short_filepath)
            if res:
                res_is_dataset = is_dataset(res)
                # Does the resource already have a DOI?
                if DOI_KEY not in res:
                    # Does resource already exist at Datacite? (a new metadata-YAML could have been autogenerated)
                    datacite_calls += 1
                    doi = dms_doi_get(res_id, short_filepath)
                    if not doi:
                        # Generate DOI and Datacite metadata record
                        datacite_calls += 1
                        doi = dms_new(res_id, res, res_is_dataset, param_test, short_filepath)
                    if doi:
                        resources[res_id][DOI_KEY] = doi
                        logger.debug("Assign DOI '%s' for '%s'", doi, short_filepath)
                        if not param_test:
                            # Add line with "doi:" to YAML
                            try:
                                with files_yaml[res_id].open(mode="r+", encoding="utf-8") as file_yaml:
                                    # Find out if last char is \n
                                    while True:
                                        char = file_yaml.read(1)
                                        if not char:
                                            break
                                        last_char_is_newline = char == "\n"
                                    if last_char_is_newline:
                                        file_yaml.write(f"doi: {doi}\n")
                                    else:
                                        file_yaml.write(f"\ndoi: {doi}\n")
                            except Exception:
                                logger.error("Error adding DOI '%s' to YAML '%s'", doi, short_filepath)
                    else:
                        logger.error("Error creating DOI '%s' for YAML '%s'", doi, short_filepath)
                elif not param_noupdate:
                    # Calls to Datacite: 1-2
                    datacite_calls += 2
                    dms_update(res_id, res, res_is_dataset, param_test, param_update, short_filepath)
        except Exception:
            logger.exception("Error when working on '%s'", short_filepath)
            sys.exit()

    # 3a. Map Collections and Resources in both directions

    # Fill dict with all resources that have parts ('collection' + 'resources')
    # or are part of collection ('in_collection').
    # All resources now have DOIs.
    # Set Datacite Metadata Schema field 12 - RelatedIdentifier
    # All previous related identifiers are removed when setting new field.

    if not param_noupdate:
        c = {}
        for res_id, res in resources.items():
            short_filepath = files_yaml[res_id].relative_to(YAML_DIR).with_suffix("")
            try:
                logger.debug("Map collections for '%s'", short_filepath)
                if get_key_value(res, "collection") and res_id not in c:
                    c[res_id] = {}
                    c[res_id][DMS_RELATION_TYPE_HASPART] = []
                member_list = res.get("resources", [])
                if member_list:
                    for member_res_id in member_list:
                        if member_res_id not in c:
                            c[member_res_id] = {}
                            c[member_res_id][DMS_RELATION_TYPE_ISPARTOF] = []
                        if res_id not in c:
                            c[res_id] = {}
                        if DMS_RELATION_TYPE_HASPART not in c[res_id]:
                            c[res_id][DMS_RELATION_TYPE_HASPART] = []
                        if member_res_id not in c[res_id][DMS_RELATION_TYPE_HASPART]:
                            c[res_id][DMS_RELATION_TYPE_HASPART].append(member_res_id)
                        if res_id not in c[member_res_id][DMS_RELATION_TYPE_ISPARTOF]:
                            c[member_res_id][DMS_RELATION_TYPE_ISPARTOF].append(res_id)
                parent_list = res.get("in_collections", [])
                if parent_list:
                    for parent_res_id in parent_list:
                        if parent_res_id not in c:
                            c[parent_res_id] = {}
                            c[parent_res_id][DMS_RELATION_TYPE_HASPART] = []
                        if res_id not in c:
                            c[res_id] = {}
                        if DMS_RELATION_TYPE_ISPARTOF not in c[res_id]:
                            c[res_id][DMS_RELATION_TYPE_ISPARTOF] = []
                        if parent_res_id not in c[res_id][DMS_RELATION_TYPE_ISPARTOF]:
                            c[res_id][DMS_RELATION_TYPE_ISPARTOF].append(parent_res_id)
                        if res_id not in c[parent_res_id][DMS_RELATION_TYPE_HASPART]:
                            c[parent_res_id][DMS_RELATION_TYPE_HASPART].append(res_id)
            except Exception:
                logger.exception("Error when mapping collections for '%s'", short_filepath)

        # 3b. Successors

        # Fill dict with all resources that have successors.
        # Set Datacite Metadata Schema field 12 - RelatedIdentifier
        #     IsObsoletedBy
        #     Obsoletes

        for res_id, res in resources.items():
            short_filepath = files_yaml[res_id].relative_to(YAML_DIR).with_suffix("")
            try:
                logger.debug("Map successors for '%s'", short_filepath)
                successor_list = res.get("successors", [])
                if successor_list:
                    if res_id not in c:
                        c[res_id] = {}
                        c[res_id][DMS_RELATION_TYPE_ISOBSOLETEDBY] = successor_list
                    else:
                        if DMS_RELATION_TYPE_ISOBSOLETEDBY not in c[res_id]:
                            c[res_id][DMS_RELATION_TYPE_ISOBSOLETEDBY] = []
                        c[res_id][DMS_RELATION_TYPE_ISOBSOLETEDBY] += successor_list
                    for successor_res_id in successor_list:
                        if successor_res_id not in c:
                            c[successor_res_id] = {}
                            c[successor_res_id][DMS_RELATION_TYPE_OBSOLETES] = [res_id]
                        else:
                            if DMS_RELATION_TYPE_ISOBSOLETEDBY not in c[successor_res_id]:
                                c[successor_res_id][DMS_RELATION_TYPE_ISOBSOLETEDBY] = []
                            c[successor_res_id][DMS_RELATION_TYPE_ISOBSOLETEDBY].append(res_id)
            except Exception:
                logger.exception("Error when mapping successors for '%s'", short_filepath)

        # 3c. Update DMS

        # All previous related identifiers are removed when setting new field
        # so all relations have to be set at the same time.

        logger.debug("Update relation metadata at Datacite")

        for res in c.items():
            short_filepath = files_yaml[res[0]].relative_to(YAML_DIR).with_suffix("")
            if datacite_calls > DATACITE_RATE_LIMIT:
                logger.debug("Rate limit reached, Sleeping...")
                time.sleep(DATACITE_RATE_LIMIT_TIMEOUT)
                datacite_calls = 0
            try:
                res_id = res[0]
                if param_test is False:
                    logger.debug("Update DMS for '%s'", short_filepath)
                    # Datacite calls: 1
                    datacite_calls += 1
                    dms_related(
                        resources,
                        res_id,
                        get_key_value(res[1], DMS_RELATION_TYPE_HASPART),
                        get_key_value(res[1], DMS_RELATION_TYPE_ISPARTOF),
                        get_key_value(res[1], DMS_RELATION_TYPE_OBSOLETES),
                        get_key_value(res[1], DMS_RELATION_TYPE_ISOBSOLETEDBY),
                        short_filepath,
                    )
            except Exception:
                logger.exception("Error when updating DMS for '%s'", filepath)


def dms_new(res_id: str, res: dict, res_is_dataset: bool, param_test: bool, filepath: str) -> str:
    """Construct DMS and call Datacite API.

    Args:
        res_id: resource id
        res: resource metadata
        res_is_dataset: whether the resource is a dataset
        param_test: test flag
        filepath: path to the resource YAML file (used for logging)

    Returns:
        DOI
    """
    # Datacite Publication Year is year of Created, else current year (https://github.com/spraakbanken/metadata-api/issues/21)
    yaml_created, yaml_updated = get_res_dates(res)

    # Construct json from metadata.
    data_json = dms_create_json(res_id, res, res_is_dataset, yaml_created, yaml_updated)

    # 5. M1. Publication date
    # Datacite Publication Year is year of Created, else current year (https://github.com/spraakbanken/metadata-api/issues/21)
    if not data_json["data"]["attributes"]["publicationYear"]:
        data_json["data"]["attributes"]["publicationYear"] = datetime.date.today().strftime("%Y")

    data_json["data"]["attributes"]["event"] = "publish"
    data_json["data"]["attributes"]["prefix"] = DMS_PREFIX

    logger.debug("Call with JSON")
    # logger.debug(json.dumps(data_json, indent=4, ensure_ascii=False))

    if not param_test:
        # Register resource
        response = requests.post(
            DMS_URL, json=data_json, headers=DMS_HEADERS, auth=HTTPBasicAuth(DMS_AUTH_USER, DMS_AUTH_PASSWORD)
        )

        logger.debug("Response %s", response.status_code)
        # logger.debug(response.json())

        doi = ""

        if response.status_code == RESPONSE_CREATED:
            d = response.json()
            if "data" in d:
                data = d["data"]
                if type(data) is list:
                    if len(data) > 0:
                        doi = data[0]["id"]
                        if len(data) > 1:
                            # This should never happen, as res_id should be unique among Språkbanken Text
                            logger.error("Multiple answers for '%s'", filepath)
                else:
                    doi = data["id"]
        else:
            logger.error("Could not create DOI for '%s': %s", filepath, response.content)
        return doi
    return ""


def dms_update(
    res_id: str, res: dict, res_is_dataset: bool, param_test: bool, param_update: bool, filepath: str
) -> bool:
    """Update existing DMS metadata.

    Args:
        res_id: resource id
        res: resource metadata
        res_is_dataset: whether the resource is a dataset
        param_test: test flag
        param_update: force update flag
        filepath: path to the resource YAML file (used for logging)

    Returns:
        True if metadata was updated, False otherwise.
    """
    updated = False

    doi = get_key_value(res, DOI_KEY)
    yaml_created, yaml_updated = get_res_dates(res)
    dms_created, dms_updated, dms_publication_year = dms_doi_get_updated(doi, filepath)

    # Only update DataCite record if it is older than YAML record
    if (dms_updated < yaml_updated or not yaml_updated) or param_update:
        if yaml_created:
            dms_created = yaml_created
        if yaml_updated:
            dms_updated = yaml_updated

        updated = True

        data_json = dms_create_json(res_id, res, res_is_dataset, dms_created, dms_updated)

        # 5. M1. Publication date
        if dms_publication_year:
            data_json["data"]["attributes"]["publicationYear"] = dms_publication_year
        else:
            data_json["data"]["attributes"]["publicationYear"] = datetime.date.today().strftime("%Y")

        logger.debug("Updating DOI '%s' for '%s'", doi, filepath)
        # logger.debug(json.dumps(data_json, indent=4, ensure_ascii=False))

        if not param_test:
            # Update resource
            url = DMS_URL + "/" + doi
            response = requests.put(
                url, json=data_json, headers=DMS_HEADERS, auth=HTTPBasicAuth(DMS_AUTH_USER, DMS_AUTH_PASSWORD)
            )

            logger.debug("Response: %s", response.status_code)
            if response.status_code >= 300:  # noqa: PLR2004
                logger.error(
                    "Error updating '%s'. DOI: '%s'. status: '%s'. data: '%s'",
                    filepath,
                    doi,
                    response.status_code,
                    data_json,
                )

    return updated


def dms_create_json(res_id: str, res: dict, res_is_dataset: bool, dms_created: str, dms_updated: str) -> dict:
    """Create JSOn data strucutre for resource.

    Args:
        res_id: resource id
        res: resource dict
        res_is_dataset: is the resource a dataset or an analysis/utility
        dms_created: creation date
        dms_updated: updated date

    Returns: Datacite records as JSON structure
    """
    # Target (landing page)
    if res_is_dataset:  # noqa: SIM108
        # corpus, lexicon, model
        dms_target = DMS_TARGET_RESOURCE_PREFIX + res_id
    else:
        # analysis/utility
        dms_target = DMS_TARGET_ANALYSIS_PREFIX + res_id

    # M - Mandatory. R - recommended. O - optional.
    # 1 - 1 value allowed. n - multiple values allowed.
    dms_json = {
        "data": {
            "type": "dois",
            "attributes": {
                # DOI target
                "url": dms_target,
            },
        }
    }

    # 2. Mn. Creator
    dms_creators = get_res_creators(res)
    dms_json["data"]["attributes"]["creators"] = dms_creators

    # 3. Mn. Title
    dms_json["data"]["attributes"]["titles"] = []
    value = get_key_value(res, "name", "swe")
    # Since 20250515 no names are given to analyses, use id instead (to make Datacite happy, since it is mandatory)
    if not value:
        value = res_id
    if value:
        dms_json["data"]["attributes"]["titles"].append({"lang": DMS_LANG_SWE, "title": value})
    value = get_key_value(res, "name", "eng")
    if not value:
        value = res_id
    if value:
        dms_json["data"]["attributes"]["titles"].append({"lang": DMS_LANG_ENG, "title": value})

    # 4. M1. Publisher
    dms_json["data"]["attributes"]["publisher"] = {
        "name": DMS_CREATOR_NAME,
        "publisherIdentifier": DMS_CREATOR_ROR,
        "publisherIdentifierScheme": "ROR",
        "schemeURI": "https://ror.org/",
    }

    # 5. M1. Publication date
    # Datacite Publication Year is year of Created, else current year (https://github.com/spraakbanken/metadata-api/issues/21)
    if dms_created:
        dms_json["data"]["attributes"]["publicationYear"] = dms_created[:4]
    else:
        dms_json["data"]["attributes"]["publicationYear"] = ""

    # 6. Rn. Subject
    dms_json["data"]["attributes"]["subjects"] = [
        {
            "subject": "Language Technology (Computational Linguistics)",
            "subjectScheme": "Standard för svensk indelning av forskningsämnen 2011",
            "classificationCode": "10208",
            "schemeURI": "https://www.scb.se/dokumentation/klassifikationer-och-standarder/standard-for-svensk-indelning-av-forskningsamnen",
        }
    ]
    # Add keywords
    keywords = get_res_keywords(res)
    if keywords:
        for keyword in keywords:
            dms_json["data"]["attributes"]["subjects"].append(keyword)

    # 7. Rn. Contributor
    # Skip

    # 8. Rn. Dates
    if dms_created or dms_updated:
        dms_json["data"]["attributes"]["dates"] = []
    if dms_created:
        dms_json["data"]["attributes"]["dates"].append({"date": dms_created, "dateType": "Created"})
    if dms_updated:
        dms_json["data"]["attributes"]["dates"].append({"date": dms_updated, "dateType": "Updated"})

    # 9. O1. Primary language
    dms_json["data"]["attributes"]["language"] = get_res_lang_code(get_key_value(res, "language_codes"))

    # 10. M1. Resource type, Type/TypeGeneral forms a pair
    dms_resource_type = get_key_value(res, "type")
    if res_is_dataset:
        # Dataset: corpus, lexicon, ...
        if get_key_value(res, "collection") is True:
            dms_resource_type_general = DMS_RESOURCE_TYPE_COLLECTION
        else:
            dms_resource_type_general = DMS_RESOURCE_TYPE_DATASET
    else:  # noqa: PLR5501
        # analysis/utility
        if get_key_value(res, "collection") is True:
            dms_resource_type_general = DMS_RESOURCE_TYPE_COLLECTION
        else:
            dms_resource_type_general = DMS_RESOURCE_TYPE_ANALYSIS
    dms_json["data"]["attributes"]["types"] = {
        "resourceType": dms_resource_type,
        "resourceTypeGeneral": dms_resource_type_general,
    }

    # 11. On. Alternate identifier
    # Resource ID (which is unique within Språkbanken Text)
    dms_json["data"]["attributes"]["alternateIdentifiers"] = [
        {"alternateIdentifierType": DMS_SLUG, "alternateIdentifier": res_id}
    ]

    # 12. Rn. Related identifier
    # Set later for collections, successors

    # 13. On. Size
    if res_is_dataset:
        value = get_res_size(get_key_value(res, "size"))
        if value:
            dms_json["data"]["attributes"]["size"] = value

    # 14. On. Formatres_id
    # Skip

    # 16. On. Rights
    if res_is_dataset:
        value = get_key_value(res, "downloads")
        if value:
            dms_json["data"]["attributes"]["rightsList"] = get_res_rights(value)
    else:
        value = get_key_value(res, "license")
        if value:
            dms_json["data"]["attributes"]["rightsList"] = get_res_rights_a(
                value, res.get("tools", []), res.get("models", [])
            )
    # 17. Rn. Descriptions
    dms_json["data"]["attributes"]["descriptions"] = []
    value_swe = get_key_value(res, "description", "swe")
    value_eng = get_key_value(res, "description", "eng")
    # Swedish
    if value_swe:
        value = value_swe
    elif value_eng:
        value = value_eng
    else:
        value = get_key_value(res, "short_description", "swe")

    if value:
        dms_description = get_clean_string(value)
        if not res_is_dataset:
            value = get_key_value(res, "example")
            dms_description += "\n" + DMS_TITLE_EXAMPLE_SWE + "\n" + get_clean_string(value)
        dms_json["data"]["attributes"]["descriptions"].append(
            {
                "lang": DMS_LANG_SWE,
                "description": dms_description.strip(),
                "descriptionType": "Abstract",
            }
        )
    # English
    if not value_eng:  # noqa: SIM108
        value = get_key_value(res, "short_description", "eng")
    else:
        value = value_eng
    if value:
        dms_description = get_clean_string(value)
        if not res_is_dataset:
            value = get_key_value(res, "example")
            dms_description += "\n" + DMS_TITLE_EXAMPLE_ENG + "\n" + get_clean_string(value)
        dms_json["data"]["attributes"]["descriptions"].append(
            {
                "lang": DMS_LANG_ENG,
                "description": dms_description.strip(),
                "descriptionType": "Abstract",
            }
        )

    # 18. Rn. Geolocation
    # Skip

    # 19. On. Funding
    # Skip

    # 20. On. Related items that don't have an ID/DOI
    # Skip

    return dms_json


def dms_related(
    resources: dict, rid: str, has_part: list, is_part_of: list, obsoletes: list, is_obsoleted_by: list, filepath: str
) -> bool:
    """Set related identifiers for resource, both collections and members.

    Args:
        resources: all resources
        rid: ID of resource.
        has_part: list of resources (resource IDs) that the entity is collection for (HasPart).
        is_part_of: list of resources (resource IDs) that the entity is a member of (IsPartOf).
        obsoletes: list of resources that are made obsoleted by entity
        is_obsoleted_by: list of resources that have made entity obsoleted
        filepath: path to the resource YAML file (used for logging)

    Returns:
        True if related identifiers were set, False otherwise.
    """
    # Get DOI of resource with related other resources
    res_doi = get_doi_from_rid(resources, rid)
    if res_doi:
        # Build list of relatedIdentifiers (HasPart)
        result = []
        for related_rid in has_part:
            doi = get_doi_from_rid(resources, related_rid)
            if doi:
                result.append(
                    {
                        "relatedIdentifierType": "DOI",
                        "relationType": DMS_RELATION_TYPE_HASPART,
                        "resourceTypeGeneral": get_res_type_str(is_dataset(resources[related_rid])),
                        "relatedIdentifier": doi,
                    }
                )
        # Build list of relatedIdentifiers (IsPartOf)
        for related_rid in is_part_of:
            doi = get_doi_from_rid(resources, related_rid)
            if doi:
                result.append(
                    {
                        "relatedIdentifierType": "DOI",
                        "relationType": DMS_RELATION_TYPE_ISPARTOF,
                        "resourceTypeGeneral": DMS_RESOURCE_TYPE_COLLECTION,
                        "relatedIdentifier": doi,
                    }
                )
        # Build list of relatedIdentifiers (Obsoletes)
        for related_rid in obsoletes:
            doi = get_doi_from_rid(resources, related_rid)
            if doi:
                result.append(
                    {
                        "relatedIdentifierType": "DOI",
                        "relationType": DMS_RELATION_TYPE_OBSOLETES,
                        "resourceTypeGeneral": get_res_type_str(is_dataset(resources[related_rid])),
                        "relatedIdentifier": doi,
                    }
                )
        # Build list of relatedIdentifiers (IsObsoletedBy)
        for related_rid in is_obsoleted_by:
            doi = get_doi_from_rid(resources, related_rid)
            if doi:
                result.append(
                    {
                        "relatedIdentifierType": "DOI",
                        "relationType": DMS_RELATION_TYPE_ISOBSOLETEDBY,
                        "resourceTypeGeneral": get_res_type_str(is_dataset(resources[related_rid])),
                        "relatedIdentifier": doi,
                    }
                )
        # Build json payload
        data_json = {
            "data": {
                "type": "dois",
                "attributes": {"relatedIdentifiers": result},
            }
        }

        logger.debug("Set related identifiers for '%s'", filepath)

        # Update resource
        url = DMS_URL + "/" + res_doi
        response = requests.put(
            url, json=data_json, headers=DMS_HEADERS, auth=HTTPBasicAuth(DMS_AUTH_USER, DMS_AUTH_PASSWORD)
        )

        logger.debug("Response: %s", response.status_code)
        # logger.debug(json.dumps(response.json(), indent=4, ensure_ascii=False))

        if response.status_code != RESPONSE_OK:
            logger.error(
                "Error setting 'related' for '%s' (status: %s, response: %s)",
                filepath,
                response.status_code,
                response.text,
            )
        return response.status_code == RESPONSE_OK
    return False


def dms_doi_get(res_id: str, filepath: str) -> str:
    """Metadata.yaml could be autogenerated, so look up if existing at DC.

    Args:
        res_id: resource id to look for
        filepath: path to the resource YAML file (used for logging)

    "alternateIdentifiers": [
    {
        "alternateIdentifierType": "slug",
        "alternateIdentifier": res_id
    },

    Confusingly it is called "identifiers" in JSON, not "alternateIdentifiers" (as in XML).

    Args:
        res_id: resource id to look for

    Returns:
        DOI or "" if res_id not found.
    """
    search_url = (
        DMS_URL
        + "?client-id="
        + DMS_REPOID
        + "&"
        + "query=identifiers.identifier:"
        + res_id
        + "%20AND%20identifiers.identifierType:"
        + DMS_SLUG
        + "&detail=true"
    )

    doi = ""

    response = requests.get(url=search_url)

    logger.debug("Get DOI from resource '%s'", filepath)
    if response.status_code == RESPONSE_OK:
        d = response.json()
        if "data" in d:
            data = d["data"]
            if type(data) is list:
                if len(data) > 0:
                    doi = data[0]["id"]
                    # if "updated" in data[0]:
                    # dms_updated = datetime.datetime.strftime(data[0]["updated"], "%Y-%m-%d")
                    if len(data) > 1:
                        # This should never happen, as res_id should be unique among Språkbanken Text
                        logger.error("Multiple answers for '%s'", filepath)
            else:
                doi = data["id"]
    return doi


def dms_doi_get_updated(doi: str, filepath: str) -> tuple[str, str, str]:
    """Get date "Created", "Updated" and "publicationYear" of a DMS record.

    Args:
        doi: DOI of resource
        filepath: path to the resource YAML file (used for logging)

    (The "updated" field from the YAML metadata, not the Datacite "updated".)

    JSON example:
        "dates": [
          {
            "date": "2017-09-13",
            "dateType": "Updated"
          }
        ],

    Args:
        doi: DOI of resource

    Returns:
        tuple[str, str, str] -- (dms_created, dms_updated, publication year)
            date for created value (eg "dates" : [{"date": "2024-06-18", "dateType": "Created"}])
            date for updated value (eg "dates" : [{"date": "2024-06-18", "dateType": "Updated"}])
            publicationYear (YYYY)

    """
    search_url = DMS_URL + "/" + doi
    # "&detail=true"

    dms_updated = ""
    dms_created = ""
    dms_publication_year = ""

    response = requests.get(
        url=search_url,
    )

    logger.debug("Get updated DOI '%s' for '%s'", doi, filepath)
    if response.status_code == RESPONSE_OK:
        d = response.json()
        if "data" in d:
            data = d["data"]
            if "attributes" in data:
                attributes = data["attributes"]
                if "publicationYear" in attributes:
                    dms_publication_year = attributes["publicationYear"]
                if "dates" in attributes:
                    dates = attributes["dates"]
                    for x in dates:
                        if x["dateType"] == "Updated":
                            dms_updated = x["date"]
                        elif x["dateType"] == "Created":
                            dms_created = x["date"]

    return dms_created, dms_updated, dms_publication_year


###############################################################################
# Helper functions
###############################################################################


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


if __name__ == "__main__":
    args = parser.parse_args()
    main(
        param_debug=args.debug,
        param_test=args.test,
        param_noupdate=args.noupdate,
        param_analyses=args.analyses,
        param_update=args.update,
        param_file=args.param_file,
    )
