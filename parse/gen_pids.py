"""Read YAML metadata files, set DOIs for resources that miss one."""

# ruff: noqa: T201 (`print` found)

import argparse
import datetime
import netrc
import re
import sys
import traceback
from pathlib import Path
from typing import Optional

import requests
import yaml
from requests.auth import HTTPBasicAuth

try:
    YAML_DIR = Path("../metadata/yaml")
    HANDLE_MAP_FILE = Path("./data/hdl2doi.tsv")
    DOI_KEY = "doi"
    DMS_URL = "https://api.datacite.org/dois"
    DMS_AUTH_USER, DMS_AUTH_ACCOUNT, DMS_AUTH_PASSWORD = netrc.netrc().authenticators("datacite.org")
    DMS_HEADERS = {"content-type": "application/json"}
    DMS_PREFIX = "10.23695"
    DMS_REPOID = "SND.SPRKB"
    DMS_CREATOR_NAME = "Språkbanken Text"
    DMS_CREATOR_ROR = "https://ror.org/03xfh2n14"
    DMS_TARGET_URL_PREFIX = "https://spraakbanken.gu.se/resurser/"
    DMS_RESOURCE_TYPE_GENERAL = "Dataset"
    DMS_RESOURCE_TYPE_COLLECTION = "Collection"
    DMS_DEFAULT_YEAR = "2024"  # Set for resources without a date
    DMS_SLUG = "slug"  # Språkbanken Texts resource ID ("slug") type
    DMS_HANDLE = "handle"
    DMS_LANG_ENG = "en"
    DMS_LANG_SWE = "sv"

    DMS_RELATION_TYPE_ISPARTOF = "IsPartOf"
    DMS_RELATION_TYPE_HASPART = "HasPart"
    DMS_RELATION_TYPE_ISOBSOLETEDBY = "IsObsoletedBy"
    DMS_RELATION_TYPE_OBSOLETES = "Obsoletes"

    RESPONSE_OK = 200
    RESPONSE_CREATED = 201

except Exception:
    print("gen_pids: Failed init. Exiting.", file=sys.stderr)
    print(traceback.format_exc(), file=sys.stderr)
    sys.exit()


# Instantiate command line arg parser
parser = argparse.ArgumentParser(
    description="Read YAML metadata files, create DOIs for those that are missing it, "
                "create and update Datacite metadata."
)
parser.add_argument("--debug", "-d", action="store_true", help="Print debug info")
parser.add_argument("--test", "-t", action="store_true", help="Test - don't write")
parser.add_argument("--noupdate", "-n", action="store_true", help="Do not update Datacite metadata, only create DOIs")
parser.add_argument("--analyses", "-a", action="store_true", help="Create Datacite metadata for analyses")


def main(param_debug: bool = False, param_test: bool = False, param_noupdate: bool = False, param_analyses: bool = False) -> None:  # noqa: D417
    """Read YAML metadata files, compile and prepare information for the API (main wrapper).

    Arguments:
        param_debug {bool} -- Print messages about what it is doing.
        param_test {bool} -- Do not modify YAML (but DMS is still created/updated).
        param_noupdate {bool} -- Do not update Datacite metadata, only create DOIs for resources without
    1. get all resources YAML metadata
    2. assign DOIs
        if metadata has no DOI
            look up in DataCite repos (using slug/name) if it exists anyway, and get DOI
            if not, put metadata into Datacite repos and get a DOI
            add DOI to YAML metadata file
        if it has DOI, update ALL information
    3. map collections and successors into relatedIdentifiers
        update Datacite repos
    """
    # 1. get all resources

    resources = {}
    files_yaml = {}

    if param_debug:
        print("gen_pids/main: Reading resources from YAML.")

    # Path.glob(pattern, *, case_sensitive=None) - returns list of found files
    # **/*.yaml - all files in this dir and subdirs, recursively
    for filepath in sorted(YAML_DIR.glob("**/*.yaml")):
        # Get resources from yaml
        try:
            res_id = filepath.stem
            files_yaml[res_id] = filepath
            with filepath.open(encoding="utf-8") as file_yaml:
                res = yaml.safe_load(file_yaml)
                if not get_key_value(res, "unlisted"):
                    res_type = get_key_value(res, "type")
                    if param_analyses:
                        # include all
                        resources[res_id] = res
                    elif res_type != "analysis" and res_type != "utility":
                        resources[res_id] = res

        except Exception:  # noqa: PERF203
            print("gen_pids/main: Error when opening YAML files. Exiting.", file=sys.stderr)
            print(traceback.format_exc(), file=sys.stderr)
            sys.exit()
    # Get list of SweClarin handles <-> res_id mappings
    """
    if param_debug:
        print("gen_pids/main: reading handles")
    handles = get_sweclarin_handles()
    """

    # 2. Assign DOIs (so both Collections and Resources have them)
    if param_debug:
        print(f"gen_pids/main: Assign DOIs to {len(resources)} resources.")
    for res_id, res in resources.items():
        if param_debug:
            print("gen_pids/main: Work on", res_id)
        if res:
            if DOI_KEY not in res:
                # Metadata.yaml could be autogenerated by Sparv
                # so look up if it already exists
                # even though resource has no DOI in metadata.
                # Unique key for a resource is res_id
                doi = dms_doi_get(res_id, param_debug)
                if not doi:
                    """
                    handle = get_key_value(handles, res_id)
                    """
                    # generate DOI
                    doi = dms_doi_create(res_id, res, param_debug, param_test)
                if doi:
                    resources[res_id][DOI_KEY] = doi
                    if param_debug:
                        print("gen_pids/main: Assign DOI for", res_id, doi)
                    if not param_test:
                        # add line with "doi:"
                        try:
                            with files_yaml[res_id].open(mode="r+", encoding="utf-8") as file_yaml:
                                # find out if last char is \n
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
                            print("gen_pids/main: Error adding DOI to YAML", res_id, doi, file=sys.stderr)
                else:
                    print("gen_pids/main: Error creating DOI for YAML", res_id, doi, file=sys.stderr)
            else:
                # The metadata already exists in DMS, so update resource (to be sure)
                """
                handle = get_key_value(handles, res_id)
                """
                if not param_noupdate:
                    dms_update(res_id, res, param_debug, param_test)

    """3a. Map Collections and Resources in both directions

    Fill dict with all resources that have parts ('collection' + 'resources')
    or are part of collection ('in_collection').
    All resources now have DOIs.
    Set Datacite Metadata Schema field 12 - RelatedIdentifier
    All previous related identifiers are removed when setting new field.

    """

    if not param_noupdate:
        c = {}
        for res_id, res in resources.items():
            try:
                if param_debug:
                    print("gen_pids/main: Map collections for", res_id)
                if get_key_value(res, "collection") and res_id not in c:
                    c[res_id] = {}
                    c[res_id][DMS_RELATION_TYPE_HASPART] = []
                member_list = get_key_list_value(res, "resources")
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
                parent_list = get_key_list_value(res, "in_collections")
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
            except Exception:  # noqa: PERF203
                print("gen_pids/main: Error when mapping collections for", res_id, file=sys.stderr)
                print(traceback.format_exc(), file=sys.stderr)

        """3b. Successors

        Fill dict with all resources that have successors.
        Set Datacite Metadata Schema field 12 - RelatedIdentifier
            IsObsoletedBy
            Obsoletes
        """

        for res_id, res in resources.items():
            try:
                if param_debug:
                    print("gen_pids/main: Map successors for", res_id)
                successor_list = get_key_list_value(res, "successors")
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
            except Exception:  # noqa: PERF203
                print("gen_pids/main: Error when mapping successors for", res_id, file=sys.stderr)
                print(traceback.format_exc(), file=sys.stderr)

        """3c. Update DMS

        All previous related identifiers are removed when setting new field
        so all relations has to be set at the same time.
        """
        if param_debug:
            print("gen_pids/main: update relation metadata at Datacite")

        for res in c.items():
            try:
                res_id = res[0]
                if param_test is False:
                    if param_debug:
                        print("gen_pids/main: Update DMS for", res_id)
                    dms_related_set(
                        resources,
                        res_id,
                        get_key_value(res[1], DMS_RELATION_TYPE_HASPART),
                        get_key_value(res[1], DMS_RELATION_TYPE_ISPARTOF),
                        get_key_value(res[1], DMS_RELATION_TYPE_OBSOLETES),
                        get_key_value(res[1], DMS_RELATION_TYPE_ISOBSOLETEDBY),
                        param_debug,
                )
            except Exception:  # noqa: PERF203
                print("gen_pids/main: Error when updating DMS for", res_id, file=sys.stderr)
                print(traceback.format_exc(), file=sys.stderr)


def dms_doi_create(res_id: str, res: dict, param_debug: bool, param_test: bool) -> str:
    """Construct DMS and call Datacite API.

    Return: DOI
    """
    # Resource type
    if get_key_value(res, "collection") is True:
        dms_resource_type = DMS_RESOURCE_TYPE_COLLECTION
        dms_resource_type_general = DMS_RESOURCE_TYPE_COLLECTION
    else:
        dms_resource_type = get_key_value(res, "type")
        dms_resource_type_general = DMS_RESOURCE_TYPE_GENERAL

    # Creators (optional)
    dms_creators = get_creators(res)

    # Construct json from metadata.
    # This is stored at Datacite and used
    # for creating a DOI.
    data_json = {
        "data": {
            "type": "dois",
            "attributes": {
                # M - Mandatory. R - recommended. O - optional.
                # 1 - 1 value allowed. n - multiple values allowed.
                # 1. M1. DOI
                "event": "publish",
                "prefix": DMS_PREFIX,
                # 2. Mn. Creator
                "creators": dms_creators,
                # 3. Mn. Title - added later
                "titles": [],
                # 4. M1. Publisher
                "publisher": {
                    "name": DMS_CREATOR_NAME,
                    "publisherIdentifier": DMS_CREATOR_ROR,
                    "publisherIdentifierScheme": "ROR",
                    "schemeURI": "https://ror.org/",
                },
                # 6. Rn. Subject
                "subjects": [
                    {
                        "subject": "Language Technology (Computational Linguistics)",
                        "subjectScheme": "Standard för svensk indelning av forskningsämnen 2011",
                        "classificationCode": "10208",
                        "schemeURI": "https://www.scb.se/dokumentation/klassifikationer-och-standarder/standard-for-svensk-indelning-av-forskningsamnen",
                    }
                ],
                # 7. Rn. Contributor (skip)
                # "contributors": [],
                # 8. Rn. Dates (added later)
                # "dates": [],
                # 9. O1. Primary language
                "language": get_res_lang_code(get_key_value(res, "language_codes")),
                # 10. M1. Resource type, Type/TypeGeneral should form a pair
                "types": {"resourceType": dms_resource_type, "resourceTypeGeneral": dms_resource_type_general},
                # 11. On. Alternate identifier
                # resource ID (which is unique within Språkbanken Text)
                "alternateIdentifiers": [{"alternateIdentifierType": DMS_SLUG, "alternateIdentifier": res_id}],
                # 12. Rn. Related identifier (set later for collections)
                # 13. On. Sizes - added later
                # 14. On. Formatres_id
                # 17. Rn. Description take short and filter HTML - added later
                "descriptions": [],
                # 18. Rn. Geolocation (skip)
                # 19. On. Funding (skip for now)
                # 20. On. Related items that don't have an ID/DOI
                # DOI target
                "url": DMS_TARGET_URL_PREFIX + res_id,
            },  # attributes
        }  # data
    }  # data_json = {

    # Add fields if they are not empty.

    # 3 - Title
    value = get_key_value(res, "name", "swe")
    if value:
        data_json["data"]["attributes"]["titles"] = []
        data_json["data"]["attributes"]["titles"].append({"lang": DMS_LANG_SWE, "title": value})
    value = get_key_value(res, "name", "eng")
    if value:
        if "titles" not in data_json["data"]["attributes"]:
            data_json["data"]["attributes"]["titles"] = []
        data_json["data"]["attributes"]["titles"].append({"lang": DMS_LANG_ENG, "title": value})

    # 5. M1. Publication date
    # Datacite Publication Year is year of Created, else current year (https://github.com/spraakbanken/metadata-api/issues/21)
    _yaml_created, yaml_updated = get_dates(res)
    if yaml_updated:
        data_json["data"]["attributes"]["publicationYear"] = yaml_updated[:4]
    else:
        # no update info, so set publication year to current year
        data_json["data"]["attributes"]["publicationYear"] = datetime.datetime.now().date().strftime("%Y")

    # 8 - Dates (optional)
    dms_created, dms_updated = get_dates(res)
    if dms_created or dms_updated:
        data_json["data"]["attributes"]["dates"] = []
    if dms_created:
        data_json["data"]["attributes"]["dates"].append({"date": dms_created, "dateType": "Created"})
    if dms_updated:
        data_json["data"]["attributes"]["dates"].append({"date": dms_updated, "dateType": "Updated"})

    # 11 - Handle
    """
    if handle:
        if "alternateIdentifiers" not in data_json["data"]["attributes"]:
            data_json["data"]["attributes"]["alternateIdentifiers"] = []
        data_json["data"]["attributes"]["alternateIdentifiers"].append(
            {
                "alternateIdentifierType": DMS_HANDLE,
                "alternateIdentifier": handle
            },
        )
    """

    # 13 - Sizes
    value = get_res_size(get_key_value(res, "size"))
    if value:
        data_json["data"]["attributes"]["size"] = value

    # 17 - Description
    value = get_key_value(res, "short_description", "swe")
    if value:
        data_json["data"]["attributes"]["descriptions"] = []
        data_json["data"]["attributes"]["descriptions"].append(
            {
                "lang": DMS_LANG_SWE,
                "description": get_clean_string(value),
                "descriptionType": "Abstract",
            }
        )
    value = get_key_value(res, "short_description", "eng")
    if value:
        if "descriptions" not in data_json["data"]["attributes"]:
            data_json["data"]["attributes"]["descriptions"] = []
        data_json["data"]["attributes"]["descriptions"].append(
            {
                "lang": DMS_LANG_ENG,
                "description": get_clean_string(value),
                "descriptionType": "Abstract",
            }
        )

    if param_debug:
        print("gen_pids/get_dms_doi: call with JSON")
        # print(json.dumps(data_json, indent=4, ensure_ascii=False))

    if not param_test:
        # Register resource
        response = requests.post(
            DMS_URL, json=data_json, headers=DMS_HEADERS, auth=HTTPBasicAuth(DMS_AUTH_USER, DMS_AUTH_PASSWORD)
        )

        if param_debug:
            print("gen_pids/get_dms_doi: response", response.status_code)
            # print(json.dumps(response.json(), indent=4, ensure_ascii=False))

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
                            print("gen_pids/get_dms_doi: Error, multiple answers for", res_id, file=sys.stderr)
                else:
                    doi = data["id"]
        else:
            print("gen_pids/get_dms_doi: Error, could not create DOI for ", res_id, response.content, file=sys.stderr)
        return doi
    else:
        return ""


def dms_update(res_id: str, res: dict, param_debug: bool, param_test: bool) -> bool:
    """Update existing DMS metadata.

    Returns:
        bool -- If metadata was updated.
    """
    updated = False

    doi = get_key_value(res, DOI_KEY)
    yaml_created, yaml_updated = get_dates(res)
    dms_created, dms_updated = dms_doi_get_updated(doi, param_debug)

    # only update DataCite record if it is older than YAML record
    if dms_updated < yaml_updated or yaml_updated == "":  # noqa: PLC1901
        if yaml_created != "":
            dms_created = yaml_created
        if yaml_updated != "":
            dms_updated = yaml_updated

        updated = True

        # Resource type
        if get_key_value(res, "collection") is True:
            dms_resource_type = DMS_RESOURCE_TYPE_COLLECTION
            dms_resource_type_general = DMS_RESOURCE_TYPE_COLLECTION
        else:
            dms_resource_type = get_key_value(res, "type")
            dms_resource_type_general = DMS_RESOURCE_TYPE_GENERAL

        # Creators (optional)
        dms_creators = get_creators(res)

        # Created and Updated
        # Datacite Publication Year is year of Created, else current year (https://github.com/spraakbanken/metadata-api/issues/21)
        if dms_created != "":
            publication_year = dms_created[:4]
        else:
            publication_year = datetime.date.today().strftime("%Y")

        data_json = {
            "data": {
                "type": "dois",
                "attributes": {
                    # M - Mandatory. R - recommended. O - optional.
                    # 1 - 1 value allowed. n - multiple values allowed.
                    # 1. M1. DOI
                    # 2. Mn. Creator
                    "creators": dms_creators,
                    # 3. Mn. Title - added later
                    # 4. M1. Publisher
                    "publisher": {
                        "name": DMS_CREATOR_NAME,
                        "publisherIdentifier": DMS_CREATOR_ROR,
                        "publisherIdentifierScheme": "ROR",
                        "schemeURI": "https://ror.org/",
                    },
                    # 5. M1. Publication date
                    "publicationYear": publication_year,
                    # 6. Rn. Subject
                    "subjects": [
                        {
                            "subject": "Language Technology (Computational Linguistics)",
                            "subjectScheme": "Standard för svensk indelning av forskningsämnen 2011",
                            "classificationCode": "10208",
                            "schemeURI": "https://www.scb.se/dokumentation/klassifikationer-och-standarder/standard-for-svensk-indelning-av-forskningsamnen",
                        }
                    ],
                    # 9. O1. Primary language
                    "language": get_res_lang_code(get_key_value(res, "language_codes")),
                    # 10. M1. Resource type, Type/TypeGeneral should form a pair
                    "types": {"resourceType": dms_resource_type, "resourceTypeGeneral": dms_resource_type_general},
                    # 11. On. Alternate identifier
                    # resource ID (which is unique within Språkbanken Text)
                    "alternateIdentifiers": [{"alternateIdentifierType": DMS_SLUG, "alternateIdentifier": res_id}],
                    # 13. On. Size. - added later
                    # 17. Rn. Description take short and filter HTML - added later
                    "descriptions": [],
                    # DOI target
                    "url": DMS_TARGET_URL_PREFIX + res_id,
                },  # attributes
            }  # data
        }

        # 3 - Title
        value = get_key_value(res, "name", "swe")
        if value:
            data_json["data"]["attributes"]["titles"] = []
            data_json["data"]["attributes"]["titles"].append({"lang": DMS_LANG_SWE, "title": value})
        value = get_key_value(res, "name", "eng")
        if value:
            if "titles" not in data_json["data"]["attributes"]:
                data_json["data"]["attributes"]["titles"] = []
            data_json["data"]["attributes"]["titles"].append({"lang": DMS_LANG_ENG, "title": value})

        # 5. M1. Publication date
        if dms_updated:
            data_json["data"]["attributes"]["publicationYear"] = dms_updated[:4]
        else:
            # no update info, so set publication year to current year
            data_json["data"]["attributes"]["publicationYear"] = datetime.datetime.now().date().strftime("%Y")

        # 8 - Dates (optional)
        if dms_created or dms_updated:
            data_json["data"]["attributes"]["dates"] = []
        if dms_created:
            data_json["data"]["attributes"]["dates"].append({"date": dms_created, "dateType": "Created"})
        if dms_updated:
            data_json["data"]["attributes"]["dates"].append({"date": dms_updated, "dateType": "Updated"})

        # 11 - Handle
        """
        if handle:
            if "alternateIdentifiers" not in data_json["data"]["attributes"]:
                data_json["data"]["attributes"]["alternateIdentifiers"] = []
            data_json["data"]["attributes"]["alternateIdentifiers"].append(
                {
                    "alternateIdentifierType": DMS_HANDLE,
                    "alternateIdentifier": handle
                },
            )
        """

        # 13 - Sizes
        value = get_res_size(get_key_value(res, "size"))
        if value:
            data_json["data"]["attributes"]["size"] = value

        # 17 - Description
        value = get_key_value(res, "short_description", "swe")
        if value:
            data_json["data"]["attributes"]["descriptions"] = []
            data_json["data"]["attributes"]["descriptions"].append(
                {
                    "lang": DMS_LANG_SWE,
                    "description": get_clean_string(value),
                    "descriptionType": "Abstract",
                }
            )
        value = get_key_value(res, "short_description", "eng")
        if value:
            if "descriptions" not in data_json["data"]["attributes"]:
                data_json["data"]["attributes"]["descriptions"] = []
            data_json["data"]["attributes"]["descriptions"].append(
                {
                    "lang": DMS_LANG_ENG,
                    "description": get_clean_string(value),
                    "descriptionType": "Abstract",
                }
            )

        if param_debug:
            print("gen_pids/dms_update: updating", res_id, doi)
            # print(json.dumps(data_json, indent=4, ensure_ascii=False))

        if not param_test:
            # Update resource
            url = DMS_URL + "/" + doi
            response = requests.put(
                url, json=data_json, headers=DMS_HEADERS, auth=HTTPBasicAuth(DMS_AUTH_USER, DMS_AUTH_PASSWORD)
            )

            if param_debug:
                print("gen_pids/dms_update: response", response.status_code)
            if response.status_code >= 300:  # noqa: PLR2004
                print("gen_pids/dms_update: Error updating", res_id, doi, response.status_code, file=sys.stderr)

    return updated


def dms_related_set(  # noqa: D417
    resources: dict,
    rid: str,
    has_part: list,
    is_part_of: list,
    obsoletes: list,
    is_obsoleted_by: list,
    param_debug: bool,
) -> bool:
    """Set related identifiers for resource, both collections and members.

    Arguments:
        rid {str} -- ID of resource.
        has_part {list} -- list of resources (resource IDs) that the entity is collection for (HasPart).
        is_part_of {list} -- list of resources (resource IDs) that the entity is a member of (IsPartOf).
        obsoletes (list) -- list of resources that are made obsoleted by entity
        is_obsoleted_by (list) -- list of resources that have made entity obsoleted

    Returns:
        bool -- Success.
    """
    # Get DOI of resource with related other resources
    res_doi = get_doi_from_rid(resources, rid)
    if (res_doi != ""):
        # Build list of relatedIdentifiers (HasPart)
        result = []
        for related_rid in has_part:
            doi = get_doi_from_rid(resources, related_rid)
            if (doi != ""):
                result.append(
                    {
                        "relatedIdentifierType": "DOI",
                        "relationType": DMS_RELATION_TYPE_HASPART,
                        "resourceTypeGeneral": DMS_RESOURCE_TYPE_GENERAL,
                        "relatedIdentifier": doi,
                    }
                )
        # Build list of relatedIdentifiers (IsPartOf)
        for related_rid in is_part_of:
            doi = get_doi_from_rid(resources, related_rid)
            if (doi != ""):
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
            if (doi != ""):
                result.append(
                    {
                        "relatedIdentifierType": "DOI",
                        "relationType": DMS_RELATION_TYPE_OBSOLETES,
                        "resourceTypeGeneral": DMS_RESOURCE_TYPE_GENERAL,
                        "relatedIdentifier": doi,
                    }
                )
        # Build list of relatedIdentifiers (IsObsoletedBy)
        for related_rid in is_obsoleted_by:
            doi = get_doi_from_rid(resources, related_rid)
            if (doi != ""):
                result.append(
                    {
                        "relatedIdentifierType": "DOI",
                        "relationType": DMS_RELATION_TYPE_ISOBSOLETEDBY,
                        "resourceTypeGeneral": DMS_RESOURCE_TYPE_GENERAL,
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

        if param_debug:
            print("gen_pids/dms_related_set: Set related identifiers for", rid)

        # Update resource
        url = DMS_URL + "/" + res_doi
        response = requests.put(
            url, json=data_json, headers=DMS_HEADERS, auth=HTTPBasicAuth(DMS_AUTH_USER, DMS_AUTH_PASSWORD)
        )

        if param_debug:
            print("gen_pids/dms_related_set: ", response.status_code)
            # print(json.dumps(response.json(), indent=4, ensure_ascii=False))

        if response.status_code != RESPONSE_OK:
            print("gen_pids/dms_related_set: Error setting related", rid, response.status_code, file=sys.stderr)

        return response.status_code == RESPONSE_OK
    else:
        return False

"""
Helper functions
"""


def get_sweclarin_handles() -> dict:
    """Read file from SweClarin mapping handles to resource IDs.

    Format: dc.identifier.uri (handle) TAB dc.source.uri (spraakbanken...) TAB dc.creator TAB dc.relation
    Ignore "isreplaceby" och "replaces" column, as well as dc.creator.

    NOTE! NOT USED!
    """
    d = {}

    with HANDLE_MAP_FILE.open() as f:
        next(f)  # skip header line
        for line in f:
            mapping = line.split("\t")
            if len(mapping) > 1 and mapping[1] != "":  # noqa: PLC1901
                res_id = mapping[1].rsplit("/", 1)[1]
                d[res_id] = mapping[0]
    return d


def get_res_lang_code(language_list: list) -> str:
    """Translate code to ISO right version."""
    if language_list:
        return language_list[0]
    return ""


def get_res_size(size_list: list) -> str:
    """Create string of resource size info."""
    result = ""
    if type(size_list) is list:
        for key, value in size_list.items():
            if result:
                result += ". " + key + ": " + value
            else:
                result = key + ": " + value
    return result


def get_res_format(downloads_list: list) -> str:
    """Create string of download URLs."""
    result = ""
    for key, value in downloads_list.items():
        if key == "format":
            if result:
                result += ", " + value
            else:
                result = value
    return result


def get_res_right(downloads_list: list) -> str:
    """Create string of resource rights information."""
    result = ""
    for key, value in downloads_list.items():
        if key == "licence":
            if result:
                result += ", "
            result = '{"rights": ' + value + '"}'
    return result


def get_creators(res: str) -> list:
    """Build creators structure."""
    # Creator is Språkbanken Text as default, but could be people
    creators = get_key_list_value(res, "creators")
    # if creators are people
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


def get_clean_string(string: str) -> str:
    """Remove HTML from string."""
    return re.sub(r"<.*?>", "", string)


def get_key_value(dictionary: dict, key: str, key2: Optional[str] = None) -> any:
    """Return key value from dictionary, else empty string."""
    if key2 is None:
        value = dictionary.get(key, "")
        return value or ""
    if key in dictionary:
        value = get_key_value(dictionary[key], key2)
        return value or ""
    return ""


def get_key_list_value(dictionary: dict, key: str) -> list:
    """Return key value from dictionary, else empty list, []."""
    return dictionary.get(key, [])


def get_dates(res: dict) -> tuple[str, str]:
    """Return 'created' and 'updated' dates as strings and check that they are valid."""
    created = get_key_value(res, "created")
    created_str = datetime.datetime.strftime(created, "%Y-%m-%d") if created else ""
    updated = get_key_value(res, "updated")
    updated_str = datetime.datetime.strftime(updated, "%Y-%m-%d") if updated else ""
    return created_str, updated_str


def get_doi_from_rid(res: dict, rid: str) -> str:  # noqa: D417
    """Return DOI belonging to a resource ID.

    Arguments:
        res {dict} -- Resources
        rid {str} -- resource ID

    Returns:
        str -- DOI or "" if rid not found.
    """
    if rid in res and "doi" in res[rid]:
        return res[rid]["doi"]
    return ""


def dms_doi_get(res_id: str, param_debug: bool) -> str:  # tuple[str, str]:
    """Metadata.yaml could be autogenerated, so look up if existing at DC.

    "alternateIdentifiers": [
    {
        "alternateIdentifierType": "slug",
        "alternateIdentifier": res_id
    },

    Confusingly it is called "identifiers" in JSON, not "alternateIdentifiers" (as in XML).

    Returns:
        str -- DOI or "" if rid not found.
        str -- date when record was last updated (string, format YYYY-MM-DD)
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
    # dms_updated = ""

    response = requests.get(
        url=search_url,
    )

    if param_debug:
        print("gen_pids/dms_doi_get: Get DOI from res id", res_id)
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
                        print("gen_pids/dms_doi_get: Error, multiple answers", res_id, file=sys.stderr)
            else:
                doi = data["id"]
    return doi  # , dms_updated


def dms_doi_get_updated(doi: str, param_debug: bool) -> tuple[str, str]:
    """Get date "Created" and "Updated" of a DMS record.

    (The "updated" field from the YAML metadata, not the Datacite "updated".)

    JSON example:
        "dates": [
          {
            "date": "2017-09-13",
            "dateType": "Updated"
          }
        ],

    Returns:
        str -- date for created value (eg "dates" : [{"date": "2024-06-18", "dateType": "Created"}])
        str -- date for updated value (eg "dates" : [{"date": "2024-06-18", "dateType": "Updated"}])

    """
    search_url = DMS_URL + "/" + doi
    # "&detail=true"

    dms_updated = ""
    dms_created = ""

    response = requests.get(
        url=search_url,
    )

    if param_debug:
        print("gen_pids/dms_doi_get_updated: Get updated ", doi)
    if response.status_code == RESPONSE_OK:
        d = response.json()
        if "data" in d:
            data = d["data"]
            if "attributes" in data:
                attributes = data["attributes"]
                if "dates" in attributes:
                    dates = attributes["dates"]
                    for x in dates:
                        if x["dateType"] == "Updated":
                            dms_updated = x["date"]
                        elif x["dateType"] == "Created":
                            dms_created = x["date"]

    return dms_created, dms_updated


def get_dms_lookup_handle(res_id: str, param_debug: bool) -> str:
    """Lookup handle for resource. If not found, return empty string.

    NOTE! NOT USED!

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

    handle = ""

    response = requests.get(
        url=search_url,
    )

    if param_debug:
        print("gen_pids/get_dms_lookup_handle", res_id, response.status_code)
    if response.status_code == RESPONSE_OK:
        d = response.json()
        if "data" in d:
            data = d["data"]
            if (
                type(data) is list
                and len(data) > 0
                and "attributes" in data[0]
                and "alternateIdentifiers" in data[0]["attributes"]
            ):
                alt_id_list = data[0]["attributes"]["alternateIdentifiers"]
                for alt_id in alt_id_list:
                    if alt_id["alternateIdentifierType"] == DMS_HANDLE:
                        handle = id["alternateIdentifier"]
    return handle


if __name__ == "__main__":
    args = parser.parse_args()
    main(param_debug=args.debug, param_test=args.test, param_noupdate=args.noupdate, param_analyses=args.analyses)
