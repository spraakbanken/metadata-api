"""Metadata utilities.

The idea is to add small reusable utility functions for working with metadata here.

Preferably run with uv, e.g.:
    uv run batch_jobs/metadata_util.py --export
    uv run batch_jobs/metadata_util.py --updated
"""

import argparse
import datetime
import logging
from pathlib import Path

import requests
import yaml

from gen_pids import dump_yaml

YAML_DIR = Path(__file__).parent.parent / "metadata" / "yaml"
DMS_TARGET_URL_PREFIX = "https://spraakbanken.gu.se/resurser/"

# Configure logger
logger = logging.getLogger("metadata_util")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
formatter = logging.Formatter("%(levelname)s: %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)

# Instantiate command line arg parser
parser = argparse.ArgumentParser(
    prog="metadata_util", description="Metadata utilities - small functions for working with metadata."
)

parser.add_argument("--export", action="store_true", help="Export some fields from all metadata into a tsv")

parser.add_argument("--updated", action="store_true", help="Update field updated based on download file date")
parser.add_argument("--add-missing-only", action="store_true", help="Only add 'updated' field if it is missing")


# -----------------------------------------------------------------------------
# Export
# -----------------------------------------------------------------------------

def get_key_value(dictionary: dict, key: str, key2: str | None = None) -> str:
    """Return value from dictionary with 'key' or 'key2' if present, else empty string."""
    if key2 is None:
        value = dictionary.get(key, "")
        return value or ""
    if key in dictionary:
        value = get_key_value(dictionary[key], key2)
        return value or ""
    return ""


def export_resources_to_tsv() -> None:
    """Export selected info of all resources."""
    file_export = Path(__file__).parent.parent / "metadata" / "export.tsv"
    export_tab = "\t"
    export_newline = "\n"

    logger.info("Exporting resource info to tsv file: '%s'", file_export)
    with file_export.open("w", encoding="utf-8") as file_csv:
        for filepath in sorted(YAML_DIR.glob("**/*.yaml")):
            res_id = filepath.stem
            with filepath.open(encoding="utf-8") as file_yaml:
                res = yaml.safe_load(file_yaml)
                res_type = "collection" if get_key_value(res, "collection") is True else get_key_value(res, "type")
                file_csv.write(get_key_value(res, "name", "swe")
                                        + export_tab + get_key_value(res, "name", "eng")
                                        + export_tab + res_type
                                        + export_tab + DMS_TARGET_URL_PREFIX + res_id
                                        + export_newline)


# -----------------------------------------------------------------------------
# Update filed 'updated'
# ------------------------------------------------------------------------------


def _get_download_date_(url: str, resource: str) -> datetime.date | None:
    """Check headers of file from url and return the last modified date."""
    res = requests.head(url)
    date = res.headers.get("Last-Modified")

    if date:
        return datetime.datetime.strptime(date, "%a, %d %b %Y %H:%M:%S %Z").date()  # .strftime("%Y-%m-%d")
    if res.status_code == 404:  # noqa: PLR2004
        logger.error("Error: Could not find downloadable for '%s': %s", resource, url)
    return None


def update_field_updated(add_missing_only: bool = False) -> None:
    """Update field 'updated' in YAML files, based on download file date.

    Add field if missing. Use modification date of the most recent downloadable data file.

    Args:
        add_missing_only: If True, only add the 'updated' field if it is missing
    """
    logger.info("Info: Updating 'updated' field in YAML files in directory: %s", YAML_DIR)
    for filepath in sorted(YAML_DIR.glob("**/*.yaml")):
        resource = f"{filepath.parent.name}/{filepath.stem}"  # Used for logging
        with filepath.open(mode="r", encoding="utf-8") as file_yaml:
            res = yaml.safe_load(file_yaml)
            updated = res.get("updated", None)

            if add_missing_only and updated is not None:
                continue

            # Save a copy of the old updated value for comparison
            old_updated = updated
            # Convert updated to date object if it is a string
            if isinstance(updated, str):
                updated = datetime.date.fromisoformat(updated)

            # Set 'updated' to date of last updated download file
            for d in res.get("downloads", []):
                url = d.get("url")
                if url:
                    date = _get_download_date_(url, resource)
                    if date and (updated is None or date > updated):
                        updated = date

        # If field 'updated' was modified or added, write back to file
        if updated is not None and str(updated) != str(old_updated):
            res["updated"] = updated
            logger.info("Info: '%s': modified field 'updated': '%s' -> '%s'", resource, old_updated, updated)
            dump_yaml.dump_with_header(filepath, res)


if __name__ == "__main__":
    args = parser.parse_args()
    if args.export:
        export_resources_to_tsv()
    if args.updated:
        update_field_updated(add_missing_only=args.add_missing_only)
