"""Read YAML metadata files, set DOIs for resources that miss one."""

import argparse  # standard
import datetime  # standard
import netrc  # standard
import re  # standard
import sys  # standard
import traceback  # standard
from pathlib import Path  # standard
from typing import Optional  # standard

import markdown  # install
import requests
import yaml
from bs4 import BeautifulSoup  # install
from requests.auth import HTTPBasicAuth

try:
    YAML_DIR = Path("../metadata/yaml")
    DOI_KEY = "doi"
    DMS_URL = "https://api.datacite.org/dois"
    DMS_AUTH_USER, DMS_AUTH_ACCOUNT, DMS_AUTH_PASSWORD = netrc.netrc().authenticators("datacite.org")
    DMS_HEADERS = {"content-type": "application/json"}
    DMS_PREFIX = "10.23695"
    DMS_REPOID = "SND.SPRKB"
    DMS_CREATOR_NAME = "Språkbanken Text"
    DMS_CREATOR_ROR = "https://ror.org/03xfh2n14"
    DMS_TARGET_RESOURCE_PREFIX = "https://spraakbanken.gu.se/resurser/"
    DMS_TARGET_ANALYSIS_PREFIX = "https://spraakbanken.gu.se/analyser/"
    DMS_RESOURCE_TYPE_DATASET = "Dataset"
    DMS_RESOURCE_TYPE_ANALYSIS = "Workflow"
    DMS_RESOURCE_TYPE_COLLECTION = "Collection"
    DMS_DEFAULT_YEAR = "2024"  # Set for resources without a date
    DMS_SLUG = "slug"  # Språkbanken Texts resource ID ("slug") type
    DMS_HANDLE = "handle"
    DMS_LANG_ENG = "en"
    DMS_LANG_SWE = "sv"
    DMS_LANG_MUL = "mul"
    DMS_TITLE_EXAMPLE_SWE = "Exempel (in English)"
    DMS_TITLE_EXAMPLE_ENG = "Example"

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
parser.add_argument("--test", "-t", action="store_true",
                    help="Test - don't write back YAML and don't call Datacite to create DOI")
parser.add_argument("--noupdate", "-n", action="store_true", help="Do not update Datacite metadata, only create DOIs")
parser.add_argument("--analyses", "-a", action="store_true", help="Create Datacite metadata for analyses")
parser.add_argument("-f", action="store", dest="param_file", type=str)


def main(param_debug: bool = False,
         param_test: bool = False,
         param_noupdate: bool = False,
         param_analyses: bool = False,
         param_file: str | None = None) -> None:
    """Read YAML metadata files, compile and prepare information for the API (main wrapper).

    Args:
        param_debug: Print messages about what it is doing.
        param_test: Do not modify YAML (but DMS is still created/updated).
        param_noupdate: Do not update Datacite metadata, only create DOIs for resources without
        param_analyses: Also process analyses/utilities and create DOI:s for them
        param_file: Pass a filename that will be handled -- else all files are read.
                            Filename built from YAML_DIR.

    1. get all resources YAML metadata
    2. assign DOIs
        if metadata has no DOI
            look up in DataCite repos (using slug/name) if it exists anyway, and get DOI
            put metadata into Datacite repos and get a DOI
            add DOI to YAML metadata file
        if it has DOI, update ALL information depending on dates
    3. map collections and successors into relatedIdentifiers
        update Datacite repos
    """
    # 1. Get all resources

    resources = {}
    files_yaml = {}

    if param_debug:
        print("gen_pids/main: Reading resources from YAML.")

    if param_file is None:
        # Path.glob(pattern, *, case_sensitive=None) - returns list of found files
        # **/*.yaml - all files in this dir and subdirs, recursively
        for filepath in sorted(YAML_DIR.glob("**/*.yaml")):
            # Get resources from yaml
            try:
                res_id = filepath.stem
                files_yaml[res_id] = filepath
                with filepath.open(encoding="utf-8") as file_yaml:
                    res = yaml.safe_load(file_yaml)
                    if not get_key_value(res, "unlisted") and (param_analyses or is_dataset(res)):
                        resources[res_id] = res

            except Exception:  # noqa: PERF203
                print(f"gen_pids/main: Error when opening/reading YAML file {filepath.stem}", file=sys.stderr)
                # print(traceback.format_exc(), file=sys.stderr)
                # sys.exit()
    else:
        filepath = YAML_DIR / param_file
        if param_debug:
            print(f"Reading from {filepath}")

        # Get resource from yaml
        try:
            res_id = filepath.stem
            files_yaml[res_id] = filepath
            with filepath.open(encoding="utf-8") as file_yaml:
                res = yaml.safe_load(file_yaml)
                if not get_key_value(res, "unlisted") and (param_analyses or is_dataset(res)):
                    resources[res_id] = res

        except Exception:
            print("gen_pids/main: Error when opening single YAML file. Exiting.", file=sys.stderr)
            print(traceback.format_exc(), file=sys.stderr)
            sys.exit()

    # 2. Assign DOIs
    if param_debug:
        print(f"gen_pids/main: Assign DOIs to {len(resources)} resources.")
    for res_id, res in resources.items():
        try:
            if param_debug:
                print("gen_pids/main: Work on", res_id)
            if res:
                res_is_dataset = is_dataset(res)
                # does the resource already have a DOI?
                if DOI_KEY not in res:
                    # does resource it already exists at Datacite? (a new metadata-YAMl could have been autogenerated)
                    doi = dms_doi_get(res_id, param_debug)
                    if not doi:
                        # generate DOI and Datacite metadata record
                        doi = dms_new(res_id, res, res_is_dataset, param_debug, param_test)
                    if doi:
                        resources[res_id][DOI_KEY] = doi
                        if param_debug:
                            print("gen_pids/main: Assign DOI for", res_id, doi)
                        if not param_test:
                            # add line with "doi:" to YAML
                            try:
                                with files_yaml[res_id].open(mode="r+", encoding="utf-8") as file_yaml:
                                    # find out if last char is \n
                                    while True:
                                        char = file_yaml.read(1)
                                        if not char:
                                            break
                                        last_char_is_newline = (char == "\n")
                                    if last_char_is_newline:
                                        file_yaml.write(f"doi: {doi}\n")
                                    else:
                                        file_yaml.write(f"\ndoi: {doi}\n")
                            except Exception:
                                print("gen_pids/main: Error adding DOI to YAML", res_id, doi, file=sys.stderr)
                    else:
                        print("gen_pids/main: Error creating DOI for YAML", res_id, doi, file=sys.stderr)
                elif not param_noupdate:
                    dms_update(res_id, res, res_is_dataset, param_debug, param_test)
        except Exception:
            print(f"gen_pids/main: Error when working on {res_id}", file=sys.stderr)
            print(traceback.format_exc(), file=sys.stderr)
            sys.exit()

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
                    dms_related(
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


def dms_new(res_id: str, res: dict, res_is_dataset: bool, param_debug: bool, param_test: bool) -> str:
    """Construct DMS and call Datacite API.

    Return: DOI
    """
    # Datacite Publication Year is year of Created, else current year (https://github.com/spraakbanken/metadata-api/issues/21)
    yaml_created, yaml_updated = get_res_dates(res)

    # Construct json from metadata.
    data_json = dms_create_json(res_id, res, res_is_dataset, yaml_created, yaml_updated)
    data_json["data"]["attributes"]["event"] = "publish"
    data_json["data"]["attributes"]["prefix"] = DMS_PREFIX

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
    else:  # noqa: RET505
        return ""


def dms_update(res_id: str, res: dict, res_is_dataset: bool, param_debug: bool, param_test: bool) -> bool:
    """Update existing DMS metadata.

    Returns:
        bool -- If metadata was updated.
    """
    updated = False

    doi = get_key_value(res, DOI_KEY)
    yaml_created, yaml_updated = get_res_dates(res)
    dms_created, dms_updated = dms_doi_get_updated(doi, param_debug)

    # only update DataCite record if it is older than YAML record
    if dms_updated < yaml_updated or not yaml_updated:
        if yaml_created:
            dms_created = yaml_created
        if yaml_updated:
            dms_updated = yaml_updated

        updated = True

        data_json = dms_create_json(res_id, res, res_is_dataset, dms_created, dms_updated)
        # 1. M1. DOI

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
                print("gen_pids/dms_update: response",
                      response.status_code)
            if response.status_code >= 300:  # noqa: PLR2004
                print("gen_pids/dms_update: Error updating",
                      res_id,
                      doi,
                      response.status_code,
                      str(data_json),
                      file=sys.stderr)

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
    if value:
        dms_json["data"]["attributes"]["titles"].append({"lang": DMS_LANG_SWE, "title": value})
    value = get_key_value(res, "name", "eng")
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
    if dms_created:  # noqa: SIM108
        publication_year = dms_created[:4]
    else:
        publication_year = datetime.date.today().strftime("%Y")
    dms_json["data"]["attributes"]["publicationYear"] = publication_year

    # 6. Rn. Subject
    dms_json["data"]["attributes"]["subjects"] = [
        {
            "subject": "Language Technology (Computational Linguistics)",
            "subjectScheme": "Standard för svensk indelning av forskningsämnen 2011",
            "classificationCode": "10208",
            "schemeURI": "https://www.scb.se/dokumentation/klassifikationer-och-standarder/standard-for-svensk-indelning-av-forskningsamnen",
        }
    ]
    # add keywords
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
        # dataset: corpus, lexicon, ...
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
        "resourceTypeGeneral": dms_resource_type_general
    }

    # 11. On. Alternate identifier
    # resource ID (which is unique within Språkbanken Text)
    dms_json["data"]["attributes"]["alternateIdentifiers"] = [
        {
            "alternateIdentifierType": DMS_SLUG,
            "alternateIdentifier": res_id
        }
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
    value = get_key_value(res, "downloads")
    if value:
        dms_json["data"]["attributes"]["rightsList"] = get_res_rights(value)

    # 17. Rn. Descriptions
    dms_json["data"]["attributes"]["descriptions"] = []
    value_swe = get_key_value(res, "description", "swe")
    value_eng = get_key_value(res, "description", "eng")
    # swedish
    if not value_swe:
        if not value_eng:  # noqa: SIM108
            value = get_key_value(res, "short_description", "swe")
        else:
            value = value_eng
    else:
        value = value_swe
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
    # english
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
    resources: dict,
    rid: str,
    has_part: list,
    is_part_of: list,
    obsoletes: list,
    is_obsoleted_by: list,
    param_debug: bool,
) -> bool:
    """Set related identifiers for resource, both collections and members.

    Args:
        resources: all resources
        rid: ID of resource.
        has_part: list of resources (resource IDs) that the entity is collection for (HasPart).
        is_part_of: list of resources (resource IDs) that the entity is a member of (IsPartOf).
        obsoletes: list of resources that are made obsoleted by entity
        is_obsoleted_by: list of resources that have made entity obsoleted
        param_debug: print information

    Returns:
        bool -- Success.
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

        if param_debug:
            print("gen_pids/dms_related: Set related identifiers for", rid)

        # Update resource
        url = DMS_URL + "/" + res_doi
        response = requests.put(
            url, json=data_json, headers=DMS_HEADERS, auth=HTTPBasicAuth(DMS_AUTH_USER, DMS_AUTH_PASSWORD)
        )

        if param_debug:
            print("gen_pids/dms_related: ", response.status_code)
            # print(json.dumps(response.json(), indent=4, ensure_ascii=False))

        if response.status_code != RESPONSE_OK:
            print("gen_pids/dms_related: Error setting related", rid, response.status_code, file=sys.stderr)

        return response.status_code == RESPONSE_OK
    else:  # noqa: RET505
        return False


def dms_doi_get(res_id: str, param_debug: bool) -> str:
    """Metadata.yaml could be autogenerated, so look up if existing at DC.

    "alternateIdentifiers": [
    {
        "alternateIdentifierType": "slug",
        "alternateIdentifier": res_id
    },

    Confusingly it is called "identifiers" in JSON, not "alternateIdentifiers" (as in XML).

    Returns:
        str -- DOI or "" if rid not found.
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
    return doi


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


"""
Helper functions
"""


def is_dataset(resource: dict) -> bool:
    """Return True is resource is a dataset (corpus, lexicon, model, training data), false if it is an analysis.

    Args:
        resource: a resource

    Returns:
        true is resource is dataset, ie not analysis/utility
    """
    return not (get_key_value(resource, "type") == "analysis" or get_key_value(resource, "type") == "utility")


def get_res_type_str(dataset: bool) -> str:
    """Return string describing resource."""
    if dataset:
        return DMS_RESOURCE_TYPE_DATASET
    else:  # noqa: RET505
        return DMS_RESOURCE_TYPE_ANALYSIS


def get_res_lang_code(language_list: list) -> str:
    """Translate code to ISO right version."""
    if language_list:
        if len(language_list) == 1:
            return language_list[0]
        else:  # noqa: RET505
            return DMS_LANG_MUL  # language_list[0]
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


def get_res_license(download_item: dict) -> dict:
    """Create item for rightsList structure.

    TODO: Add schema etc (right now we only send free text)

    Returns:
        rightsList item
    """
    rights = download_item["licence"]  # eg "CC BY 4.0"

    return {"rights": rights}


def get_res_rights(downloads_list: list) -> dict:
    """Create dict of resource rights information.

    Returns:
        rightsList item (or empty dict)
    """
    result_set = set()
    for item in downloads_list:
        rights = item.get("licence", "")
        if rights:
            result_set.add(rights)
    return [{"rights": rights} for rights in result_set]


def get_res_creators(res: str) -> list:
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


def get_res_keywords(res: dict) -> list:
    """Build keywords structure."""
    keywords = get_key_list_value(res, "keywords")
    if keywords:  # noqa: SIM108
        dms_keywords = [
            {"subject": keyword,
             "subjectScheme": "keyword"}
            for keyword in keywords]
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
            # assume type is date
            created_str = datetime.datetime.strftime(created, "%Y-%m-%d") if created else ""
    else:
        created_str = ""

    updated = get_key_value(res, "updated")
    if updated:
        if type(updated) is str:
            updated_str = updated
        else:
            # assume type is date
            updated_str = datetime.datetime.strftime(updated, "%Y-%m-%d") if updated else ""
    else:
        updated_str = ""
    return created_str, updated_str


def get_clean_string(string: str) -> str:
    """Remove HTML etc from string."""
    # value = re.sub('<[^>]+>', '', value) # remove HTML tags
    # value = re.sub(r'\n\s*\n', '\n\n', value) # remove multiple newlines
    # return re.sub(r"<.*?>", "", string)

    # handle beginning-of-code quotes, eg ```xml
    md = re.sub(r"(^\s*```)[^\s`]+\n", r"\1", string, flags=re.MULTILINE)
    # transform from markdown to HTML
    html = markdown.markdown(md)
    # let BS export clean text
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text()
    # remove multiple newlines
    return re.sub(r"\n\s*\n", "\n\n", text)


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


if __name__ == "__main__":
    args = parser.parse_args()
    main(param_debug=args.debug,
         param_test=args.test,
         param_noupdate=args.noupdate,
         param_analyses=args.analyses,
         param_file=args.param_file)
