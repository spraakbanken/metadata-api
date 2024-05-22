"""Read YAML metadata files, set DOIs for resources that miss one."""

import argparse
import json
import netrc
import re
import sys
import traceback
import urllib.parse
from collections import defaultdict
from pathlib import Path

import requests
import yaml
from requests.auth import HTTPBasicAuth

# from collections import defaultdict
# from translate_lang import get_lang_names
# from datacite import DataCiteMDSClient, schema45

try:
    YAML_DIR = Path("metadata/yaml") # TODO, should be ../
    DOI_KEY = "doi"
    DMS_URL = "https://api.datacite.org/dois"
    DMS_AUTH_USER, DMS_AUTH_ACCOUNT, DMS_AUTH_PASSWORD = netrc.netrc().authenticators("example.com")  # TODO: error checking
    DMS_HEADERS = {"content-type": "application/json"}
    DMS_PREFIX = "10.23695"
    DMS_REPOID = "SND.SPRKB"
    DMS_CREATOR_NAME = "Språkbanken Text"
    DMS_CREATOR_ROR = "https://ror.org/12345"  # TODO
    DMS_TARGET_URL_PREFIX = "https://spraakbanken.gu.se/resurser/"
    DMS_RESOURCE_TYPE_GENERAL = "Dataset"
    DMS_RESOURCE_TYPE_COLLECTION = "Collection"
    DMS_DEFAULT_YEAR = "2024" # TODO later
    DMS_SLUG = "slug" # Språkbanken Texts resource ID ("slug") type

    DMS_RELATION_TYPE_ISPARTOF = 'IsPartOf'
    DMS_RELATION_TYPE_HASPART = 'HasPart'
    DMS_RELATION_TYPE_ISOBSOLETEDBY = 'IsObsoletedBy'
    DMS_RELATION_TYPE_OBSOLETES = 'Obsoletes'

    RESPONSE_OK = 200
    RESPONSE_CREATED = 201

except Exception as e:
    print("Error: failed init.")
    print(traceback.format_exc())
    sys.exit()


"""Test repo"""
# TODO remove after test
DMS_URL = "https://api.test.datacite.org/dois"
DMS_PREFIX = "10.80338"
DMS_REPOID = "PMAL.RUSOIT"
DMS_AUTH_USER = DMS_REPOID
DMS_AUTH_PASSWORD = "spraakbanken7!"

# Instantiate command line arg parser
parser = argparse.ArgumentParser(description="Read YAML metadata files, create DOIs for those that are missing it, create and update Datacite metadata.")
parser.add_argument("--debug", "-d", action="store_true", help="Print debug info")
parser.add_argument("--test", "-t", action="store_true", help="Test - don't write")


def str_presenter(dumper, data):
    """Configure yaml package for dumping multiline strings (for preserving format).

    # https://github.com/yaml/pyyaml/issues/240
    # https://pythonhint.com/post/9957829820118202/yamldump-adding-unwanted-newlines-in-multiline-strings
    # Ref: https://stackoverflow.com/questions/8640959/how-can-i-control-what-scalar-form-pyyaml-uses-for-my-data
    """
    if data.count("\n") > 0:  # check for multiline string
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)


yaml.add_representer(str, str_presenter)
yaml.representer.SafeRepresenter.add_representer(str, str_presenter)


class IndentDumper(yaml.Dumper):
    """Indent list items (for preserving format).

    https://reorx.com/blog/python-yaml-tips/#enhance-list-indentation-dump
    """

    def increase_indent(self, flow=False, indentless=False):  # noqa: D102, ANN201, ANN001
        return super(IndentDumper, self).increase_indent(flow, False)  # noqa


def main(param_debug: bool=True, param_test: bool=True) -> None:
    """Read YAML metadata files, compile and prepare information for the API (main wrapper)."""
    resources = {}  # set, not possible to change items

    # 1. get all resources

    resources = {}
    files_yaml = {}

    if param_debug:
        print("main: reading resources YAML")

    # Path.glob(pattern, *, case_sensitive=None) - returns list of found files
    # **/*.yaml - all files in this dir and subdirs, recursively
    # https://python.land/data-processing/python-yaml#Reading_and_parsing_a_YAML_file_with_Python
    for filepath in sorted(YAML_DIR.glob("**/*.yaml")):
        # Get resources from yaml
        # TODO error handling
        res_id = filepath.stem
        files_yaml[res_id] = filepath
        with filepath.open(encoding="utf-8") as file_yaml:
            res = yaml.safe_load(file_yaml)
            if not get_key_value(res, "unlisted") == True:
                resources[res_id] = res
 
    # Get list of SweClarin handles <-> res_id mappings
    if param_debug:
        print("main: reading handles")
    handles = get_sweclarin_handles()

    # 2. Assign DOIs (so both Collections and Resources have them)
    # TODO Error handling, loggingFalses_id, res)
    if param_debug:
        print("main: assign DOIs")
    for res_id, res in resources.items():
        if res:
            if DOI_KEY not in res:
                # Metadata.yaml could be autogenerated, so look up if it already exists
                # even though resource has no DOI in metadata
                # Unique key for a resource is res_id
                doi = get_dms_lookup_doi(res_id,
                                         param_debug)
                if not doi:
                    # gen DOI
                    handle = get_key_value(handles, res_id)
                    doi = get_dms_doi(res_id, 
                                      res, 
                                      handle, 
                                      param_debug)
                if doi:
                    resources[res_id][DOI_KEY] = doi
                    if param_debug:
                        print("main: assign DOI", res_id, doi)
                else:
                    if param_debug:
                        print("main: could not assign DOI key", res_id, doi)
            else:
                # The metadata already exists in DMS, so update it (to be sure)
                handle = get_key_value(handles, res_id)
                dms_update(res_id, 
                    res, 
                    handle, 
                    param_debug)

    """3. Save as YAML (prev json)"""
    if param_debug:
        print("main: save YAML")

    if not param_test:
        for res_id, res in resources.items():
            if res:
                with files_yaml[res_id].open("w") as file_yaml:
                    yaml.dump(
                        res,
                        file_yaml,
                        Dumper=IndentDumper, 
                        sort_keys=False, 
                        default_flow_style=False, 
                        allow_unicode=True
                    )

    """4. Map Collections and Resources in both directions

    Fill dict with all resources that have parts ('collection' + 'resources')
    or are part of collection ('in_collection').
    All resources now have DOIs.
    Set Datacite Metadata Schema field 12 - RelatedIdentifier
    All previous related identifiers are removed when setting new field.

    """
    if param_debug:
        print("main: map collections and resources")

    c = dict()
    for res_id, res in resources.items():
        if get_key_value(res, "collection"):
            if res_id not in c:
                c[res_id] = dict()
                c[res_id][DMS_RELATION_TYPE_HASPART] = []
        member_list = get_key_list_value(res, "resources")
        if member_list:
            for member_res_id in member_list:
                if member_res_id not in c:
                    c[member_res_id] = dict()
                    c[member_res_id][DMS_RELATION_TYPE_ISPARTOF] = []
                if DMS_RELATION_TYPE_HASPART not in c[res_id]:
                    c[res_id][DMS_RELATION_TYPE_HASPART] = []
                if member_res_id not in c[res_id][DMS_RELATION_TYPE_HASPART]:
                    c[res_id][DMS_RELATION_TYPE_HASPART].append(member_res_id)
                if res_id not in c[member_res_id][DMS_RELATION_TYPE_ISPARTOF]:
                    c[member_res_id][DMS_RELATION_TYPE_ISPARTOF].append(res_id)
        parent_list = get_key_list_value(res, "in_collection")
        if parent_list:
            for parent_res_id in parent_list:
                if parent_res_id not in c:
                    c[parent_res_id] = dict()
                    c[parent_res_id][DMS_RELATION_TYPE_HASPART] = []
                if DMS_RELATION_TYPE_ISPARTOF not in c[res_id]:
                    c[res_id][DMS_RELATION_TYPE_ISPARTOF] = []
                if parent_res_id not in c[res_id][DMS_RELATION_TYPE_ISPARTOF]:
                    c[res_id][DMS_RELATION_TYPE_ISPARTOF].append(parent_res_id)
                if res_id not in c[parent_res_id][DMS_RELATION_TYPE_HASPART]:
                    c[parent_res_id][DMS_RELATION_TYPE_HASPART].append(res_id)

    """4b. Sucessors
    
    Fill dict with all resources that have successors.
    XML:
    successors:
        - sweanalogy
    Set Datacite Metadata Schema field 12 - RelatedIdentifier
        IsObsoletedBy
        Obsoletes
    """
    if param_debug:
        print("main: map obsoleted/successors")

    for res_id, res in resources.items():
        successor_list = get_key_list_value(res, "successors")
        if successor_list:
            if res_id not in c:
                c[res_id] = dict()
                c[res_id][DMS_RELATION_TYPE_ISOBSOLETEDBY] = successor_list
            else:
                c[res_id][DMS_RELATION_TYPE_ISOBSOLETEDBY] += successor_list
            for successor_res_id in successor_list:
                if successor_res_id not in c:
                    c[successor_res_id] = dict()
                    c[successor_res_id][DMS_RELATION_TYPE_OBSOLETES] = [res_id]
                else:
                    c[successor_res_id][DMS_RELATION_TYPE_OBSOLETES].append(res_id)

    """Update DMS

    All previous related identifiers are removed when setting new field
    so all relations has to be set at the same time.
    """
    if param_debug:
        print("main: update DC metadata")

    for res in c.items():
        res_id = res[0]
        # if not param_test:
        # TODO
        set_dms_related(resources,
                        res_id,
                        get_key_value(res[1], DMS_RELATION_TYPE_HASPART),
                        get_key_value(res[1], DMS_RELATION_TYPE_ISPARTOF),
                        get_key_value(res[1], DMS_RELATION_TYPE_OBSOLETES),
                        get_key_value(res[1], DMS_RELATION_TYPE_ISOBSOLETEDBY),
                        param_debug
                        )
    

    # TODO successors



def get_dms_doi(res_id: str, res: str, handle: str, param_debug: bool) -> str:
    """Construct DMS and call Datacite API."""

    if get_key_value(res, "collection") == True:
        dms_resource_type = DMS_RESOURCE_TYPE_COLLECTION
        dms_resource_type_general = DMS_RESOURCE_TYPE_COLLECTION
    else:
        dms_resource_type = get_key_value(res, "type")
        dms_resource_type_general = DMS_RESOURCE_TYPE_GENERAL

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
                "creators": [
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
                ],
                # 3. Mn. Title
                "titles": [
                    {
                        "lang": "se",
                        "title": get_key_value(res, "name", "swe")
                    },
                    {
                        "lang": "en",
                        "title": get_key_value(res, "name", "eng")
                    },
                ],
                # 4. M1. Publisher
                "publisher": {
                    "name": DMS_CREATOR_NAME,
                    "publisherIdentifier": DMS_CREATOR_ROR,
                    "publisherIdentifierScheme": "ROR",
                    "schemeURI": "https://ror.org/",
                },
                # 5. M1. Publication date
                "publicationYear": DMS_DEFAULT_YEAR,
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
                "contributors": [],
                # 8. Rn. Dates (skip for now)
                "dates": [],
                # 9. O1. Primary language
                "language": get_res_lang_code(get_key_value(res, "language_codes")),
                # 10. M1. Resource type, Type/TypeGeneral should form a pair
                "types": {
                    "resourceType": dms_resource_type,
                    "resourceTypeGeneral": dms_resource_type_general
                    },
                # 11. On. Alternate identifier
                # resource ID (which is unique within Språkbanken Text)
                "alternateIdentifiers": [
                    {
                        "alternateIdentifierType": DMS_SLUG, 
                        "alternateIdentifier": res_id
                    },
                    {
                        "alternateIdentifierType": "Handle",
                        "alternateIdentifier": handle
                    }
                ],
                # 12. Rn. Related identifier (set later for collections)
                "relatedIdentifiers": [],
                # 13. On. Size.
                "sizes": [get_res_size(get_key_value(res, "size"))],
                # 14. On. Formatres_id
                # 17. Rn. Description take short and filter HTML
                "descriptions": [
                    {
                        "lang": "se",
                        "description": get_clean_string(get_key_value(res, "short_description", "swe")),
                        "descriptionType": "Abstract",
                    },
                    {
                        "lang": "en",
                        "description": get_clean_string(get_key_value(res, "short_description", "eng")),
                        "descriptionType": "Abstract",
                    },
                ],
                # 18. Rn. Geolocation (skip)
                "geoLocations": [],
                # 19. On. Funding (skip for now)
                "fundingReferences": [], 
                # 20. On. Related items that don't have an ID/DOI
                "relatedItems": [],
                # DOI target
                "url": DMS_TARGET_URL_PREFIX + res_id,
            },  # attributes
        }  # data
    }

    if param_debug:
        print("get_dms_doi: call with JSON")
        print(json.dumps(data_json, indent=4, ensure_ascii=False))

    # TODO Validate

    # Register resource
    response = requests.post(
        DMS_URL, json=data_json, headers=DMS_HEADERS, auth=HTTPBasicAuth(DMS_AUTH_USER, DMS_AUTH_PASSWORD)
    )

    if param_debug:
        print("get_dms_doi: response")
        print(json.dumps(response.json(), indent=4, ensure_ascii=False))

    doi = ""
    
    # TODO what if it already exists? It shouldn't, because this only gets called if resources has a DOI key...
    # status_code: 201 // response["reason"] = "Created"
    if response.status_code == RESPONSE_CREATED:
        d = response.json()
        if "data" in d:
            data = d["data"]
            if type(data) is list:
                if (len(data) > 0):
                    doi = data[0]["id"]
                    if (len(data) > 1):
                        # TODO This should never happen, as res_id should be unique among Språkbanken Text
                        print("ERROR get_dms_doi: multiple answers.")
            else:
                doi = data["id"]

    else:
        print("get_dms_doi: Could not create DOI for ", res_id)
        print(response.content)

    return doi



def dms_update(res_id: str, res: str, handle: str, param_debug: bool) -> int:
    """Construct DMS and call Datacite API."""

    doi = get_key_value(res, DOI_KEY)

    if get_key_value(res, "collection") == True:
        dms_resource_type = DMS_RESOURCE_TYPE_COLLECTION
        dms_resource_type_general = DMS_RESOURCE_TYPE_COLLECTION
    else:
        dms_resource_type = get_key_value(res, "type")
        dms_resource_type_general = DMS_RESOURCE_TYPE_GENERAL

    data_json = {
        "data": {
            "type": "dois",
            "attributes": {
                # M - Mandatory. R - recommended. O - optional.
                # 1 - 1 value allowed. n - multiple values allowed.
                # 1. M1. DOI
                # 2. Mn. Creator
                "creators": [
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
                ],
                # 3. Mn. Title - added later
                # 4. M1. Publisher
                "publisher": {
                    "name": DMS_CREATOR_NAME,
                    "publisherIdentifier": DMS_CREATOR_ROR,
                    "publisherIdentifierScheme": "ROR",
                    "schemeURI": "https://ror.org/",
                },
                # 5. M1. Publication date
                "publicationYear": DMS_DEFAULT_YEAR,
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
                "types": {
                    "resourceType": dms_resource_type,
                    "resourceTypeGeneral": dms_resource_type_general
                    },
                # 11. On. Alternate identifier
                # resource ID (which is unique within Språkbanken Text)
                "alternateIdentifiers": [
                    {
                        "alternateIdentifierType": DMS_SLUG, 
                        "alternateIdentifier": res_id
                    },
                    {
                        "alternateIdentifierType": "Handle",
                        "alternateIdentifier": handle
                    }
                ],
                # 13. On. Size.
                "sizes": [get_res_size(get_key_value(res, "size"))],
                # 17. Rn. Description take short and filter HTML
                "descriptions": [
                    {
                        "lang": "se",
                        "description": get_clean_string(get_key_value(res, "short_description", "swe")),
                        "descriptionType": "Abstract",
                    },
                    {
                        "lang": "en",
                        "description": get_clean_string(get_key_value(res, "short_description", "eng")),
                        "descriptionType": "Abstract",
                    },
                ],
                # DOI target
                "url": DMS_TARGET_URL_PREFIX + res_id,
            },  # attributes
        }  # data
    }

    # 3 - Title
    value = get_key_value(res, "name", "swe")
    if value:
        data_json["data"]["attributes"]["titles"] = []
        data_json["data"]["attributes"]["titles"].append(
            {
                "lang": "se",
                "title": value
            }
        )
    value = get_key_value(res, "name", "eng")
    if value:
        if "titles" not in data_json["data"]["attributes"]:
            data_json["data"]["attributes"]["titles"] = []
        data_json["data"]["attributes"]["titles"].append(
            {
                "lang": "en",
                "title": value
            }
        )
    # 11 - Handle
    if handle:
        if "alternateIdentifiers" not in data_json["data"]["attributes"]:
            data_json["data"]["attributes"]["alternateIdentifiers"] = []
        data_json["data"]["attributes"]["alternateIdentifiers"].append(
            {
                "alternateIdentifierType": "Handle",
                "alternateIdentifier": handle
            },
        )
    # 17 - Description
    value = get_key_value(res, "short_description", "swe")
    if value:
        data_json["data"]["attributes"]["descriptions"] = []
        data_json["data"]["attributes"]["descriptions"].append(
            {
                "lang": "se",
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
                "lang": "en",
                "description": get_clean_string(value),
                "descriptionType": "Abstract",
            }
        )

    if param_debug:
        print("dms_update: updating", res_id, doi)
        print(json.dumps(data_json, indent=4, ensure_ascii=False))

    # Update resource
    url = DMS_URL + "/" + doi
    response = requests.put(
        url, json=data_json, headers=DMS_HEADERS, auth=HTTPBasicAuth(DMS_AUTH_USER, DMS_AUTH_PASSWORD)
    )

    if param_debug:
        print("dms_update: response ", response.status_code)

    return response.status_code



def set_dms_related(resources: dict, rid: str, 
                    has_part: list, is_part_of: list,
                    obsoletes: list, is_obsoleted_by: list,
                    param_debug: bool) -> bool:
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
    # Build list of relatedIdentifiers (HasPart)
    result = []
    for related_rid in has_part:
        doi = get_doi_from_rid(resources, related_rid)
        result.append({
            "relatedIdentifierType": "DOI", 
            "relationType": DMS_RELATION_TYPE_HASPART, 
            "resourceTypeGeneral": DMS_RESOURCE_TYPE_GENERAL,
            "relatedIdentifier": doi
        })


    # Build list of relatedIdentifiers (IsPartOf)
    #result = ""
    for related_rid in is_part_of:
        doi = get_doi_from_rid(resources, related_rid)
        result.append({
            "relatedIdentifierType": "DOI", 
            "relationType": DMS_RELATION_TYPE_ISPARTOF, 
            "resourceTypeGeneral": DMS_RESOURCE_TYPE_COLLECTION,
            "relatedIdentifier": doi
        })
    # Build list of relatedIdentifiers (Obsoletes)
    #result = ""
    for related_rid in obsoletes:
        doi = get_doi_from_rid(resources, related_rid)
        result.append({
            "relatedIdentifierType": "DOI", 
            "relationType": DMS_RELATION_TYPE_OBSOLETES, 
            "resourceTypeGeneral": DMS_RESOURCE_TYPE_GENERAL,
            "relatedIdentifier": doi
        })
    # Build list of relatedIdentifiers (IsObsoletedBy)
    #result = ""
    for related_rid in is_obsoleted_by:
        doi = get_doi_from_rid(resources, related_rid)
        result.append({
            "relatedIdentifierType": "DOI", 
            "relationType": DMS_RELATION_TYPE_ISOBSOLETEDBY, 
            "resourceTypeGeneral": DMS_RESOURCE_TYPE_GENERAL,
            "relatedIdentifier": doi
        })
    # Build json payload
    data_json = {
        "data": {
            "type": "dois",
            "attributes": {
                "relatedIdentifiers": result
            },
        }
    }

    if param_debug:
        print("dms_set_dms_related: ", data_json)

    # Update resource
    # TODO urllib.parse.quote() necessary?
    #url = DMS_URL + "/" + urllib.parse.quote(get_doi_from_rid(resources, rid), safe='')
    url = DMS_URL + "/" + get_doi_from_rid(resources, rid)
    response = requests.put(
        url,
        json=data_json,
        headers=DMS_HEADERS,
        auth=HTTPBasicAuth(DMS_AUTH_USER, DMS_AUTH_PASSWORD)
    )
    """
    headers = {
    "content-type": "application/json",
    "authorization": "Basic UE1BTC5SVVNPSVQ6c3ByYWFrYmFua2VuNyE="
    }
    response = requests.put(url, json=data_json, headers=headers)
    """

    if param_debug:
        print(json.dumps(response.json(), indent=4, ensure_ascii=False))

    return response.status_code == RESPONSE_OK



"""
Helper functions
"""


def get_sweclarin_handles() -> dict:
    """read file from SweClarin mapping handles to resource IDs

        Format: dc.identifier.uri (handle) TAB dc.source.uri (spraakbanken...) TAB dc.creator TAB dc.relation
        Ignore "isreplaceby" och "replaces" column, as well as dc.creator.
    """

    d = {}
    
    with open("parse/data/hdl2doi.tsv") as f:
        next(f) # skip header line
        for line in f:
            mapping = line.split("\t")
            if (len(mapping) > 1):
                if (mapping[1] != ""):
                    res_id = mapping[1].rsplit('/', 1)[1]
                    d[res_id] = mapping[0]
    return d


def get_res_lang_code(language_list: list) -> str:
    """Translate code to ISO right version."""
    if language_list:
        return language_list[0]
    else:
        pass


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


def get_clean_string(string: str) -> str:
    """Remove HTML from string."""
    return re.sub(r"<.*?>", "", string)


def get_key_value(dictionary: dict, key: str, key2: str = None) -> str:
    """Return key value from dictionary, else empty string."""
    if (key2 == None):
        value = dictionary.get(key, "")
        return value if value else ""
    else:
        if key in dictionary:
            value = get_key_value(dictionary[key], key2) 
            return value if value else ""
        else:
            return ""

def get_key_list_value(dictionary: dict, key: str) -> list:
    """Return key value from dictionary, else empty list, []."""
    return dictionary.get(key, [])


def get_doi_from_rid(res: dict, rid: str) -> str:
    """Return DOI belonging to a resource ID.

    Arguments:
        res {dict} -- Resources
        rid {str} -- resource ID

    Returns:
        str -- DOI or "" if rid not found.
    """
    if rid in res:
        if 'doi' in res[rid]:
            return res[rid]['doi']
    return ""


def get_dms_lookup_doi(res_id: str, param_debug: bool) -> str:
    """Metadata.yaml could be autogenerated, so look up if existing at DC.
    "alternateIdentifiers": [
    {
        "alternateIdentifierType": "resource ID",
        "alternateIdentifier": res_id
    },

    Is "identifiers" in JSON, not "alternateIdentifiers"

    """
    search_url = DMS_URL + \
        "?" + \
        "query=identifiers.identifier:" + res_id + \
        "%20AND%20identifiers.identifierType:" + DMS_SLUG + \
        "&detail=true"

    doi = ""

    response = requests.get(
        url = search_url,
    )

    if param_debug:
        print("get_dms_lookup_doi:", response.status_code)
    if response.status_code == 200: # TODO
        d = response.json()
        if "data" in d:
            data = d["data"]
            # TODO always a list, but could be empty, so test len(data) > 0
            if type(data) is list:
                if (len(data) > 0):
                    doi = data[0]["id"]
                    if (len(data) > 1):
                        # TODO This should never happen, as res_id should be unique among Språkbanken Text
                        print("ERROR get_dms_lookup_doi: multiple answers.")
            else:
                doi = data["id"]
    return doi


if __name__ == "__main__":
    args = parser.parse_args()
    main(param_debug = args.debug, param_test = args.test)
