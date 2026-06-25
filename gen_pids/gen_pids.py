"""Read YAML metadata files, assign missing DOIs via DataCite, and update DataCite metadata.

- Created DOIs are written back to YAML.
- Updates of the DataCite metadata includes collection/successor relationships and updated timestamps.
- Pushes changes in YAML files to Git repository.
- Does log rotation.

The script supports flags to run in dry-run mode, limit updates or force updates.

Usage with uv:
    uv run -m gen_pids.gen_pids [--debug] [--dry-run | --no-update | --force-update] [-f FILENAME]

Usage with a virtual environment:
    python -m gen_pids.gen_pids [--debug] [--dry-run | --no-update | --force-update] [-f FILENAME]
"""

import argparse
import datetime
import logging
import sys
from pathlib import Path

import yaml

from gen_pids import dump_yaml, git_utils, log_utils, utils
from gen_pids.datacite import DataCiteClient, build_datacite_client
from gen_pids.settings import (
    DMS_AUTH_PASSWORD,
    DMS_CREATOR_NAME,
    DMS_CREATOR_ROR,
    DMS_LANG_ENG,
    DMS_LANG_SWE,
    DMS_PREFIX,
    DMS_RELATION_TYPE_HASPART,
    DMS_RELATION_TYPE_ISOBSOLETEDBY,
    DMS_RELATION_TYPE_ISPARTOF,
    DMS_RELATION_TYPE_OBSOLETES,
    DMS_REPOID,
    DMS_RESOURCE_TYPE_ANALYSIS,
    DMS_RESOURCE_TYPE_COLLECTION,
    DMS_RESOURCE_TYPE_DATASET,
    DMS_SLUG,
    DMS_TARGET_ANALYSIS_PREFIX,
    DMS_TARGET_RESOURCE_PREFIX,
    DMS_TITLE_EXAMPLE_ENG,
    DMS_TITLE_EXAMPLE_SWE,
    DOI_KEY,
    LOG_DIR,
    RESPONSE_CREATED,
    RESPONSE_OK,
    YAML_DIR,
)

# Setup logging
logger = logging.getLogger("gen_pids")

# Instantiate command line arg parser
parser = argparse.ArgumentParser(
    description="Read YAML metadata files, create DOIs for those that are missing it, "
    "create and update Datacite metadata."
)
parser.add_argument("--debug", "-d", action="store_true", help="Print debug info")
mode_group = parser.add_mutually_exclusive_group()
mode_group.add_argument(
    "--dry-run",
    "-t",
    action="store_true",
    help="Do not write back YAML metadata and do not create/update records at Datacite",
)
mode_group.add_argument(
    "--no-update",
    "-n",
    action="store_true",
    help="Do not update Datacite metadata, only create DOIs for resources without them",
)
mode_group.add_argument("--force-update", "-u", action="store_true", help="Force update of metadata at Datacite")
parser.add_argument(
    "--file",
    "-f",
    action="store",
    dest="single_file",
    type=str,
    help="Process only the given YAML file, e.g. 'lexicon/saldo.yaml'. "
    "With --force-update, collection and successor updates are limited to the selected resource's dependency closure.",
)


def main(
    debug: bool = False,
    dry_run: bool = False,
    no_update: bool = False,
    force_update: bool = False,
    single_file: str | None = None,
) -> None:
    """Read YAML metadata files, compile and prepare information for the API (main wrapper).

    Args:
        debug: Print messages about what it is doing.
        dry_run: Do not write back YAML metadata or create/update records at Datacite.
        no_update: Do not update Datacite metadata, only create DOIs for resources without them.
        force_update: Force update of metadata at Datacite.
        single_file: Pass a filename that will be handled -- else all files are read.

    1. Read metadata from YAML file(s)
    2. Build relation map for collections and successors (relatedIdentifiers) (offline)
    3. Assign DOIs
        if metadata has no DOI
            look up in DataCite repos (using slug/name) if it exists anyway, and get DOI
            put metadata into Datacite repos and get a DOI
            add DOI to YAML metadata file
        if it has DOI, update ALL information depending on dates
    4. Update Datacite repos with relatedIdentifiers
    5. Commit and push changes to Git repository
    6. Remove logs older than 6 months
    """
    if debug:
        logger.setLevel(logging.DEBUG)

    if sum([dry_run, no_update, force_update]) > 1:
        logger.error("Use only one of --dry-run, --no-update, or --force-update.")
        sys.exit(2)

    log_utils.configure_logging(LOG_DIR, logger)

    if DMS_AUTH_PASSWORD:
        logger.info("Using credentials from settings.py (user: %s) for DataCite client.", DMS_REPOID)
        datacite_client = DataCiteClient(DMS_REPOID, DMS_AUTH_PASSWORD, logger)
    else:
        logger.info("Using credentials from netrc for DataCite client.")
        datacite_client = build_datacite_client(logger)

    if dry_run:
        logger.info("Running in dry-run mode - no YAML writes and no Datacite writes.")
    elif no_update:
        logger.info(
            "Running in no-update mode - existing Datacite metadata will not be updated, "
            "but DOIs will be created for resources missing them."
        )
    elif force_update:
        logger.info("Running in force-update mode - eligible Datacite metadata will be updated.")

    yaml_paths = {}  # YAML file paths {resource_id: filepath, ...}
    all_resources = {}  # All resources {resource_id: resource_dict, ...}
    process_resources = all_resources  # Resources to process, all by default
    related_resources = None  # Relation mapping to update, all by default
    read_all_resources = True  # Whether to read all resources or just a specific one
    res_id = ""  # Resource ID of the single file to process, if applicable
    read_resource_count = 0

    # 1. Read metadata from YAML file(s)
    logger.debug("Reading resources from YAML...")

    if single_file is not None:
        # Quit early if file does not exist
        filepath = YAML_DIR / single_file
        res_id = filepath.stem
        if not filepath.exists():
            logger.error("File '%s' does not exist. Exiting.", filepath)
            sys.exit(2)
        read_resource_file(filepath, all_resources, yaml_paths)
        read_resource_count += 1
        process_resources = {res_id: all_resources[res_id]}

        # In most cases we need to read all YAML files because of collections and successors,
        # but if no-update is enabled and the file is not a collection, we can skip the rest.
        is_collection = filepath.parent.relative_to(YAML_DIR) == "collection"
        if no_update and not is_collection:
            read_all_resources = False

    if read_all_resources:
        # Read all YAML files
        for filepath in sorted(YAML_DIR.glob("**/*.yaml")):
            if single_file is not None and filepath == YAML_DIR / single_file:
                continue  # already read above
            read_resource_file(filepath, all_resources, yaml_paths)
            read_resource_count += 1

    logger.info("Read %d resources from YAML.", read_resource_count)

    if not no_update:
        # 2. Build relation map for collections and successors (relatedIdentifiers)
        related_resources = build_related_resource_map(all_resources, yaml_paths)
        if single_file is not None and force_update:
            closure_ids = get_related_resource_closure(res_id, related_resources)
            process_resources = {resource_id: all_resources[resource_id] for resource_id in closure_ids}
            related_resources = filter_related_resource_map(related_resources, closure_ids)
            # Get IDs of related resources, excluding the resource itself
            related_list = [relation for relation in related_resources if relation != res_id]
            logger.info(
                "Limiting force-update to '%s' and its dependencies (%d resources).",
                single_file,
                len(related_list),
            )

    # 3. Assign DOIs, add new data to Datacite, do dms_update for resources that already have DOIs
    assign_doi(process_resources, all_resources, yaml_paths, datacite_client, dry_run, no_update, force_update)
    if not no_update:
        if dry_run:
            logger.info("Dry run: not updating relation metadata at Datacite.")
        else:
            # 4. Update Datacite repos with relatedIdentifiers
            update_dms_related(all_resources, yaml_paths, related_resources or {}, datacite_client)

    if dry_run:
        logger.info("Dry run: skipping git commit and push.")
    else:
        # 5. Commit and push changes to Git repository
        git_utils.commit_metadata_changes()

    # 6. Remove logs older than 6 months
    log_utils.rotate_logs(LOG_DIR, logger)


def read_resource_file(filepath: Path, all_resources: dict, yaml_paths: dict) -> None:
    """Read a YAML resource file and add it to yaml_paths and all_resources if applicable.

    Args:
        filepath: Path to the YAML file.
        all_resources: dictionary of all resources
        yaml_paths: dictionary of YAML file paths
    """
    try:
        res_id = filepath.stem
        yaml_paths[res_id] = filepath
        with filepath.open(encoding="utf-8") as file_yaml:
            res = yaml.safe_load(file_yaml)
            if not utils.get_key_value(res, "unlisted"):
                all_resources[res_id] = res
    except Exception:
        logger.exception("Error when opening/reading YAML file '%s'", filepath)


def build_related_resource_map(all_resources: dict, yaml_paths: dict) -> dict:
    """Build the full relation map for collections and successors."""
    related_resources = map_collections(all_resources, yaml_paths)
    map_successors(all_resources, yaml_paths, related_resources)
    return related_resources


def get_related_resource_closure(seed_res_id: str, related_resources: dict) -> set[str]:
    """Return the transitive closure of collection/successor relations for a resource."""
    closure = {seed_res_id}
    pending = [seed_res_id]

    while pending:
        res_id = pending.pop()
        for related_ids in related_resources.get(res_id, {}).values():
            for related_res_id in related_ids:
                if related_res_id not in closure:
                    closure.add(related_res_id)
                    pending.append(related_res_id)

    return closure


def filter_related_resource_map(related_resources: dict, resource_ids: set[str]) -> dict:
    """Restrict the relation map to a selected set of resources."""
    return {
        res_id: {
            relation_type: [related_res_id for related_res_id in related_ids if related_res_id in resource_ids]
            for relation_type, related_ids in relations.items()
        }
        for res_id, relations in related_resources.items()
        if res_id in resource_ids
    }


def assign_doi(
    process_resources: dict,
    all_resources: dict,
    yaml_paths: dict,
    datacite_client: DataCiteClient,
    dry_run: bool,
    no_update: bool,
    force_update: bool,
) -> None:
    """Assign DOI to resource if it does not have one, else update metadata at Datacite.

    Args:
        process_resources: dictionary of resources to process
        all_resources: dictionary of all resources
        yaml_paths: dictionary of YAML file paths
        datacite_client: DataCite client instance
        dry_run: flag indicating dry-run mode
        no_update: flag indicating no update mode
        force_update: flag indicating force update mode
    """
    logger.debug("Checking DOIs for %d resources...", len(process_resources))
    if dry_run:
        logger.info("Dry run: skipping update checks.")
    for res_id, res in process_resources.items():
        filepath = yaml_paths[res_id]
        short_filepath = filepath.relative_to(YAML_DIR).with_suffix("")
        try:
            logger.debug("Checking DOI for resource '%s'", short_filepath)
            if res:
                res_is_dataset = utils.is_dataset(res)
                # Does the resource already have a DOI?
                if DOI_KEY not in res:
                    # Does resource already exist at Datacite? (DOI may have been deleted from YAML)
                    doi = dms_doi_get(res_id, short_filepath, datacite_client)
                    if not doi:
                        # Generate DOI and Datacite metadata record
                        if dry_run:
                            logger.debug("Dry run: would create DOI for '%s'", short_filepath)
                            continue
                        doi = dms_new(res_id, res, res_is_dataset, short_filepath, datacite_client)
                        if not doi:
                            logger.error("Error creating DOI '%s' for YAML '%s'", doi, short_filepath)
                            continue

                    if not dry_run:
                        # Update YAML with new DOI
                        logger.debug("Assign DOI '%s' for '%s'", doi, short_filepath)
                        all_resources[res_id][DOI_KEY] = doi
                        try:
                            dump_yaml.dump_with_header(filepath, all_resources[res_id])
                        except Exception:
                            logger.error("Error adding DOI '%s' to YAML '%s'", doi, short_filepath)
                elif not no_update:
                    if dry_run:
                        # Skip update check in dry-run mode
                        continue
                    # DOI found: update existing DMS metadata
                    dms_update(res_id, res, res_is_dataset, force_update, short_filepath, datacite_client)
        except Exception:
            logger.exception("Error while working on DOI for '%s'", short_filepath)
            sys.exit(2)

    logger.info("Checked DOIs for %d resources.", len(process_resources))


def map_collections(all_resources: dict, yaml_paths: dict) -> dict:
    """Map collections and resources in both directions.

    Fill dict with all resources that have parts ('collection' + 'resources')
    or are part of collection ('in_collection').
    All resources now have DOIs.
    Set Datacite Metadata Schema field 12 - RelatedIdentifier
    All previous related identifiers are removed when setting new field.

    Args:
        all_resources: dictionary of all resources
        yaml_paths: dictionary of YAML file paths

    Returns:
        collection mapping dictionary
    """
    logger.debug("Mapping collections and resources...")
    collections = {}
    collections_count = 0
    in_collections_count = 0

    for res_id, res in all_resources.items():
        short_filepath = yaml_paths[res_id].relative_to(YAML_DIR).with_suffix("")
        try:
            if utils.get_key_value(res, "collection") and res_id not in collections:
                collections[res_id] = {}
                collections[res_id][DMS_RELATION_TYPE_HASPART] = []
            member_list = utils.expand_res_ref(res.get("resources", []), all_resources)
            if member_list:
                # logger.debug("Map resources for collection '%s'", short_filepath)
                collections_count += 1
                for member_res_id in member_list:
                    if member_res_id not in collections:
                        collections[member_res_id] = {}
                        collections[member_res_id][DMS_RELATION_TYPE_ISPARTOF] = []

                    if DMS_RELATION_TYPE_HASPART not in collections[res_id]:
                        collections[res_id][DMS_RELATION_TYPE_HASPART] = []
                    if member_res_id not in collections[res_id][DMS_RELATION_TYPE_HASPART]:
                        collections[res_id][DMS_RELATION_TYPE_HASPART].append(member_res_id)
                    if res_id not in collections[member_res_id][DMS_RELATION_TYPE_ISPARTOF]:
                        collections[member_res_id][DMS_RELATION_TYPE_ISPARTOF].append(res_id)
            parent_list = res.get("in_collections", [])
            if parent_list:
                # logger.debug("Map in_collections for resource '%s'", short_filepath)
                in_collections_count += len(parent_list)
                for parent_res_id in parent_list:
                    if parent_res_id not in collections:
                        collections[parent_res_id] = {}
                        collections[parent_res_id][DMS_RELATION_TYPE_HASPART] = []
                    if res_id not in collections:
                        collections[res_id] = {}
                    if DMS_RELATION_TYPE_ISPARTOF not in collections[res_id]:
                        collections[res_id][DMS_RELATION_TYPE_ISPARTOF] = []
                    if parent_res_id not in collections[res_id][DMS_RELATION_TYPE_ISPARTOF]:
                        collections[res_id][DMS_RELATION_TYPE_ISPARTOF].append(parent_res_id)
                    if res_id not in collections[parent_res_id][DMS_RELATION_TYPE_HASPART]:
                        collections[parent_res_id][DMS_RELATION_TYPE_HASPART].append(res_id)
        except Exception:
            logger.exception("Error when mapping collections for '%s'", short_filepath)

    logger.info("Mapped %d collections and %d in_collections.", collections_count, in_collections_count)

    return collections


def map_successors(all_resources: dict, yaml_paths: dict, collections: dict) -> None:
    """Map successors.

    Fill collections dict with all resources that have successors.
    Set Datacite Metadata Schema field 12 - RelatedIdentifier
        IsObsoletedBy
        Obsoletes

    Args:
        all_resources: dictionary of all resources
        yaml_paths: dictionary of YAML file paths
        collections: collection mapping dictionary
    """
    logger.debug("Mapping successors...")
    successor_count = 0
    for res_id, res in all_resources.items():
        short_filepath = yaml_paths[res_id].relative_to(YAML_DIR).with_suffix("")
        try:
            successor_list = res.get("successors", [])
            if successor_list:
                successor_count += 1
                # logger.debug("Map successors for '%s'", short_filepath)
                utils.ensure_collection_entry(collections, res_id, DMS_RELATION_TYPE_ISOBSOLETEDBY)
                collections[res_id][DMS_RELATION_TYPE_ISOBSOLETEDBY] += successor_list
                for successor_res_id in successor_list:
                    utils.ensure_collection_entry(collections, successor_res_id, DMS_RELATION_TYPE_OBSOLETES)
                    collections[successor_res_id][DMS_RELATION_TYPE_OBSOLETES].append(res_id)
        except Exception:
            logger.exception("Error when mapping successors for '%s'", short_filepath)
    logger.info("Mapped %d succeeded resources.", successor_count)


def update_dms_related(
    all_resources: dict, yaml_paths: dict, related_resources: dict, datacite_client: DataCiteClient
) -> None:
    """Update DMS related identifiers for collections and successors.

    All previous related identifiers are removed when setting new field so all relations have to be set at the same
    time.

    Args:
        all_resources: dictionary of all resources
        yaml_paths: dictionary of YAML file paths
        related_resources: dictionary of resources with related identifiers
        datacite_client: DataCite client instance
    """
    logger.info("Update relation metadata at Datacite.")

    for res in related_resources.items():
        short_filepath = yaml_paths[res[0]].relative_to(YAML_DIR).with_suffix("")
        try:
            res_id = res[0]
            res_doi = utils.get_doi_from_rid(all_resources, res_id)
            if not res_doi:
                logger.debug("Skipping related-identifier update for '%s' (missing DOI)", short_filepath)
                continue
            logger.debug("Update DMS for '%s'", short_filepath)
            dms_related(
                all_resources,
                res_doi,
                utils.get_key_value(res[1], DMS_RELATION_TYPE_HASPART),
                utils.get_key_value(res[1], DMS_RELATION_TYPE_ISPARTOF),
                utils.get_key_value(res[1], DMS_RELATION_TYPE_OBSOLETES),
                utils.get_key_value(res[1], DMS_RELATION_TYPE_ISOBSOLETEDBY),
                short_filepath,
                datacite_client,
            )
        except Exception:
            logger.exception("Error when updating DMS for '%s'", short_filepath)


def dms_new(res_id: str, res: dict, res_is_dataset: bool, filepath: str, datacite_client: DataCiteClient) -> str:
    """Construct DMS and call Datacite API.

    Args:
        res_id: resource id
        res: resource metadata
        res_is_dataset: whether the resource is a dataset
        filepath: path to the resource YAML file (used for logging)
        datacite_client: DataCite client instance

    Returns:
        DOI
    """
    # Datacite Publication Year is year of Created, else current year (https://github.com/spraakbanken/metadata-api/issues/21)
    yaml_created, yaml_updated = utils.get_res_dates(res)

    # Construct json from metadata.
    data_json = dms_create_json(res_id, res, res_is_dataset, yaml_created, yaml_updated)

    # 5. M1. Publication date
    # Datacite Publication Year is year of Created, else current year (https://github.com/spraakbanken/metadata-api/issues/21)
    if not data_json["data"]["attributes"]["publicationYear"]:
        data_json["data"]["attributes"]["publicationYear"] = datetime.date.today().strftime("%Y")

    data_json["data"]["attributes"]["event"] = "publish"
    data_json["data"]["attributes"]["prefix"] = DMS_PREFIX

    # Register resource
    logger.info("Calling Datacite API to create DOI for '%s'", filepath)
    # logger.debug(json.dumps(data_json, indent=4, ensure_ascii=False))
    response = datacite_client.create_doi(data_json)
    # logger.debug("Response %s", response.status_code)
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


def dms_update(
    res_id: str, res: dict, res_is_dataset: bool, force_update: bool, filepath: str, datacite_client: DataCiteClient
) -> bool:
    """Update existing DMS metadata.

    Args:
        res_id: resource id
        res: resource metadata
        res_is_dataset: whether the resource is a dataset
        force_update: force update flag
        filepath: path to the resource YAML file (used for logging)
        datacite_client: DataCite client instance

    Returns:
        True if metadata was updated, False otherwise.
    """
    updated = False

    doi = utils.get_key_value(res, DOI_KEY)
    yaml_created, yaml_updated = utils.get_res_dates(res)
    dms_created, dms_updated, dms_publication_year = dms_doi_get_updated(doi, filepath, datacite_client)

    # Only update DataCite record if it is older than YAML record or if 'force_update' is True
    if (dms_updated < yaml_updated or not yaml_updated) or force_update:
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

        # Update resource
        logger.info("Updating data at Datacite for resource '%s' (DOI '%s')", filepath, doi)
        # import json
        # logger.debug(json.dumps(data_json["data"]["attributes"], indent=2, ensure_ascii=False))
        response = datacite_client.update_doi(doi, data_json)

        if response.status_code >= 300:  # noqa: PLR2004
            logger.error(
                "Error updating '%s'. DOI: '%s'. status: '%s'. data: '%s'",
                filepath,
                doi,
                response.status_code,
                data_json,
            )
        else:
            logger.debug("Response from Datacite: %s", response.status_code)

    return updated


def dms_create_json(res_id: str, res: dict, res_is_dataset: bool, dms_created: str, dms_updated: str) -> dict:
    """Create JSON data structure for resource.

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
    dms_creators = utils.get_res_creators(res)
    dms_json["data"]["attributes"]["creators"] = dms_creators

    # 3. Mn. Title
    dms_json["data"]["attributes"]["titles"] = []
    value = utils.get_key_value(res, "name", "swe")
    # Since 20250515 no names are given to analyses, use id instead (to make Datacite happy, since it is mandatory)
    if not value:
        value = res_id
    if value:
        dms_json["data"]["attributes"]["titles"].append({"lang": DMS_LANG_SWE, "title": value})
    value = utils.get_key_value(res, "name", "eng")
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
    keywords = utils.get_res_keywords(res)
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
    dms_json["data"]["attributes"]["language"] = utils.get_res_lang_code(utils.get_key_value(res, "language_codes"))

    # 10. M1. Resource type, Type/TypeGeneral forms a pair
    dms_resource_type = utils.get_key_value(res, "type")
    if res_is_dataset:
        # Dataset: corpus, lexicon, ...
        if utils.get_key_value(res, "collection") is True:
            dms_resource_type_general = DMS_RESOURCE_TYPE_COLLECTION
        else:
            dms_resource_type_general = DMS_RESOURCE_TYPE_DATASET
    else:  # noqa: PLR5501
        # analysis/utility
        if utils.get_key_value(res, "collection") is True:
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
        value = utils.get_res_size(utils.get_key_value(res, "size"))
        if value:
            dms_json["data"]["attributes"]["size"] = value

    # 14. On. Formatres_id
    # Skip

    # 16. On. Rights
    rights_list = utils.get_res_rights(res, res_is_dataset)
    if rights_list:
        dms_json["data"]["attributes"]["rightsList"] = rights_list
    # 17. Rn. Descriptions
    dms_json["data"]["attributes"]["descriptions"] = []
    value_swe = utils.get_key_value(res, "description", "swe")
    value_eng = utils.get_key_value(res, "description", "eng")
    # Swedish
    if value_swe:
        value = value_swe
    elif value_eng:
        value = value_eng
    else:
        value = utils.get_key_value(res, "short_description", "swe")

    if value:
        dms_description = utils.get_clean_string(value)
        if not res_is_dataset:
            value = utils.get_key_value(res, "example")
            dms_description += "\n" + DMS_TITLE_EXAMPLE_SWE + "\n" + utils.get_clean_string(value)
        dms_json["data"]["attributes"]["descriptions"].append(
            {
                "lang": DMS_LANG_SWE,
                "description": dms_description.strip(),
                "descriptionType": "Abstract",
            }
        )
    # English
    if not value_eng:  # noqa: SIM108
        value = utils.get_key_value(res, "short_description", "eng")
    else:
        value = value_eng
    if value:
        dms_description = utils.get_clean_string(value)
        if not res_is_dataset:
            value = utils.get_key_value(res, "example")
            dms_description += "\n" + DMS_TITLE_EXAMPLE_ENG + "\n" + utils.get_clean_string(value)
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
    res_doi: str,
    has_part: list,
    is_part_of: list,
    obsoletes: list,
    is_obsoleted_by: list,
    filepath: str,
    datacite_client: DataCiteClient,
) -> bool:
    """Set related identifiers for resource, both collections and members.

    Args:
        resources: all resources
        res_doi: DOI for the resource.
        has_part: list of resources (resource IDs) that the entity is collection for (HasPart).
        is_part_of: list of resources (resource IDs) that the entity is a member of (IsPartOf).
        obsoletes: list of resources that are made obsoleted by entity
        is_obsoleted_by: list of resources that have made entity obsoleted
        filepath: path to the resource YAML file (used for logging)
        datacite_client: DataCite client instance

    Returns:
        True if related identifiers were set, False otherwise.
    """
    # Get DOI of resource with related other resources
    if res_doi:
        # Build list of relatedIdentifiers (HasPart)
        result = []
        for related_rid in has_part:
            doi = utils.get_doi_from_rid(resources, related_rid)
            if doi:
                result.append(
                    {
                        "relatedIdentifierType": "DOI",
                        "relationType": DMS_RELATION_TYPE_HASPART,
                        "resourceTypeGeneral": utils.get_res_type_str(utils.is_dataset(resources[related_rid])),
                        "relatedIdentifier": doi,
                    }
                )
        # Build list of relatedIdentifiers (IsPartOf)
        for related_rid in is_part_of:
            doi = utils.get_doi_from_rid(resources, related_rid)
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
            doi = utils.get_doi_from_rid(resources, related_rid)
            if doi:
                result.append(
                    {
                        "relatedIdentifierType": "DOI",
                        "relationType": DMS_RELATION_TYPE_OBSOLETES,
                        "resourceTypeGeneral": utils.get_res_type_str(utils.is_dataset(resources[related_rid])),
                        "relatedIdentifier": doi,
                    }
                )
        # Build list of relatedIdentifiers (IsObsoletedBy)
        for related_rid in is_obsoleted_by:
            doi = utils.get_doi_from_rid(resources, related_rid)
            if doi:
                result.append(
                    {
                        "relatedIdentifierType": "DOI",
                        "relationType": DMS_RELATION_TYPE_ISOBSOLETEDBY,
                        "resourceTypeGeneral": utils.get_res_type_str(utils.is_dataset(resources[related_rid])),
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

        # Update resource
        logger.info("Set related identifiers for '%s'", filepath)
        response = datacite_client.update_doi(res_doi, data_json)

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


def dms_doi_get(res_id: str, filepath: str, datacite_client: DataCiteClient) -> str:
    """Metadata file could be autogenerated and DOI may have been deleted, so look up if existing at DataCite.

    Args:
        res_id: resource id to look for
        filepath: path to the resource YAML file (used for logging)
        datacite_client: DataCite client instance

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
    doi = ""

    logger.debug("Searching for resource id '%s' at Datacite", res_id)
    response = datacite_client.get_doi_by_slug(res_id)

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


def dms_doi_get_updated(doi: str, filepath: str, datacite_client: DataCiteClient) -> tuple[str, str, str]:
    """Get date "Created", "Updated" and "publicationYear" of a DMS record.

    Args:
        doi: DOI of resource
        filepath: path to the resource YAML file (used for logging)
        datacite_client: DataCite client instance

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
    dms_updated = ""
    dms_created = ""
    dms_publication_year = ""

    logger.debug("Get DataCite metadata for DOI '%s' (%s)", doi, filepath)
    response = datacite_client.get_record(doi)

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


if __name__ == "__main__":
    args = parser.parse_args()
    main(
        debug=args.debug,
        dry_run=args.dry_run,
        no_update=args.no_update,
        force_update=args.force_update,
        single_file=args.single_file,
    )
