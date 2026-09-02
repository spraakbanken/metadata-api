"""Util functions used by the metadata API."""

from __future__ import annotations

import datetime
import json
import logging
import os
import tomllib
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

import jsonschema_rs
import requests
from mkdocs.commands import build
from mkdocs.config import load_config

from metadata_api.settings import settings

if TYPE_CHECKING:
    from pymemcache.client.base import Client

logger = logging.getLogger(__name__)


# Define ResourceTypes enum from settings
ResourceTypes = Enum("ResourceTypes", {name: name for name in settings.RESOURCE_TYPES}, type=str)


def load_json(json_path: Path, prefix: str = "", cache_client: Client | None = None) -> dict[str, Any]:
    """Load data from cache if available, otherwise load from JSON file.

    Args:
        json_path: The path to the JSON file to load.
        prefix: The prefix to add to keys.
        cache_client: Memcache client to use.

    Returns:
        Dictionary containing the loaded data.
    """
    if not cache_client:
        logger.warning("No memcache client available.")
        return read_static_json(json_path)

    jsonfile = json_path.name
    cache_key = add_prefix(jsonfile, prefix)

    try:
        data = cache_client.get(cache_key)
    except Exception:
        logger.exception("Error reading key '%s' from cache; falling back to disk", cache_key)
        return read_static_json(json_path)

    if not data:
        # Populate cache if it's empty
        logger.debug("Data for '%s' not found in cache. Reloading.", cache_key)
        all_data = read_static_json(json_path)
        try:
            cache_client.set(cache_key, list(all_data.keys()))
            for k, v in all_data.items():
                cache_client.set(add_prefix(k, prefix), v)
        except Exception:
            logger.exception("Error populating cache; continuing without cache")
            return all_data
    else:
        # Load individual items from cache
        all_data: dict[str, Any] = {}
        for k in data:
            try:
                all_data[k] = cache_client.get(add_prefix(k, prefix))
            except Exception:
                logger.exception("Error reading key '%s' from cache; skipping", add_prefix(k, prefix))

    return all_data


def get_single_resource(
    resource_id: str, resources_dict: dict[str, Any], cache_client: Client | None = None
) -> dict[str, Any]:
    """Get resource from resource dictionaries and add long resource description if available.

    Args:
        resource_id: The ID of the resource.
        resources_dict: Dictionary of resources.
        cache_client: Memcache client to use.

    Returns:
        Dictionary containing the resource.
    """
    resource_texts = load_json(
        settings.STATIC / settings.RESOURCE_TEXTS_FILE,
        prefix="res_descr",
        cache_client=cache_client,
    )
    long_description = resource_texts.get(resource_id, {})

    resource = {}
    for resource_dict in resources_dict.values():
        if resource_id in resource_dict:
            resource = resource_dict[resource_id]
            break

    if resource and long_description:
        resource["description"] = long_description

    return resource


def load_resources(resource_files: list[str], static_path: Path, cache_client: Client | None = None) -> dict[str, Any]:
    """Load all resource types from JSON from cache or files.

    Args:
        resource_files: List of JSON files to load.
        static_path: Path to the static folder.
        cache_client: Memcache client to use.
        legacy: Whether to use legacy keys (True) or singular keys (False).

    Returns:
        Dictionary containing resource dictionaries.
    """
    resources = {}
    for res_file in resource_files:
        resources[res_file[:-5]] = load_json(static_path / res_file, cache_client=cache_client)
    return resources


def read_static_json(json_path: Path) -> dict[str, Any]:
    """Load json file from static folder and return as object.

    Args:
        json_path: Path to the JSON file.

    Returns:
        Dictionary containing the JSON data.
    """
    logger.info("Reading json %s", json_path)
    try:
        with json_path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error("File not found: %s", json_path)
        return {}
    except json.JSONDecodeError:
        logger.error("Error reading JSON file: %s", json_path)
        return {}


def add_prefix(key: str, prefix: str) -> str:
    """Add prefix to key.

    Args:
        key: The key to add a prefix to.
        prefix: The prefix to add.

    Returns:
        The key with the prefix added.
    """
    if prefix:
        key = f"{prefix}_{key}"
    return key


def dict_to_list(input_obj: dict[str, Any]) -> list:
    """Convert resource dict into list.

    Args:
        input_obj: The dictionary to convert.

    Returns:
        List of dictionary values.
    """
    # return sorted(input.values(), key=lambda x: locale.strxfrm(x.get("name_sv")))
    return list(input_obj.values())


def get_bibtex(resource_id: str, resources_dict: dict[str, Any]) -> str:
    """Get BibTeX entry for a resource.

    Args:
        resource_id: The ID of the resource.
        resources_dict: Dictionary of resources.

    Returns:
        BibTeX entry as a string.
    """
    for resource_type in resources_dict.values():
        if resource_id in resource_type:
            return create_bibtex(resource_type[resource_id])
    return "Error: Resource not found"


def create_bibtex(resource: dict[str, Any]) -> str:
    """Create bibtex record for resource.

    Args:
        resource: The resource dictionary.

    Returns:
        BibTeX entry as a string.
    """
    f_doi = resource.get("doi", "")
    f_id = resource.get("id", "")  # id/slug/maskinnamn
    f_creators = resource.get("creators", [])  # creators, "Skapad av"
    f_author = " and ".join(f_creators) if len(f_creators) > 0 else "Språkbanken Text"
    f_words = resource.get("keywords", [])
    f_words.insert(0, "Language Technology (Computational Linguistics)")
    f_keywords = ", ".join(f_words)
    f_languages = resource.get("languages", [])
    if len(f_languages) > 0:
        f_language = f_languages[0].get("code", "")
        for item in f_languages[1:]:
            f_language += ", " + item.get("code", "")
    else:
        f_language = ""
    f_title = resource["name"].get("eng", "")
    if f_title:
        f_title = resource["name"].get("swe", "")
    # Get year, fallback to current year
    f_year = str(datetime.datetime.now().date().year)
    f_updated = resource.get("updated", "")
    if f_updated:
        f_year = f_updated[:4]
    else:
        f_created = resource.get("created", "")
        if f_created:
            f_year = f_created[:4]

    # Target URL
    match resource["type"]:
        case "analysis" | "utility":
            f_url = "https://spraakbanken.gu.se/analyser/"
        case "corpus" | "lexicon" | "model":
            f_url = "https://spraakbanken.gu.se/resurser/"
        case _:
            # Fallback
            f_url = "https://spraakbanken.gu.se/resurser/"

    # Build bibtex string
    return (
        f"@misc{{{f_id},\n"
        f"  doi = {{{f_doi}}},\n"
        f"  url = {{{f_url}{f_id}}},\n"
        f"  author = {{{f_author}}},\n"
        f"  keywords = {{{f_keywords}}},\n"
        f"  language = {{{f_language}}},\n"
        f"  title = {{{f_title}}},\n"
        f"  publisher = {{Språkbanken Text}},\n"
        f"  year = {{{f_year}}}\n"
        "}"
    )


def send_to_slack(message: str, slack_webhook: str) -> None:
    """Send message to Slack.

    Args:
        message: The message to send.
        slack_webhook: The Slack webhook URL.
    """
    if not slack_webhook:
        logger.warning("No Slack webhook configured.")
        return
    try:
        requests.post(slack_webhook, json={"text": message})
    except Exception as e:
        logger.error("Error sending message to Slack, %s", e)
        logger.exception("Error sending message to Slack")


def get_version_from_pyproject(path: Path = Path("pyproject.toml")) -> str:
    """Get the version of the project from the pyproject.toml file.

    Args:
        path: Path to the pyproject.toml file.
    """
    # Get absolute path
    path = path.resolve()
    if not path.exists() or not path.is_file():
        logger.error("Could not find pyproject.toml file at %s", path)
        raise FileNotFoundError(f"Could not find pyproject.toml file at {path}")
    with path.open("rb") as f:
        data = tomllib.load(f)
    return data["project"]["version"]


def get_schema_validator(filepath: Path) -> jsonschema_rs.Validator | None:
    """Load the JSON schema from the given file path and return a validator."""
    try:
        with filepath.open(encoding="utf-8") as schema_file:
            schema = json.load(schema_file)
            validator = jsonschema_rs.validator_for(schema)
    except Exception:
        logger.exception("Failed to get schema '%s'", filepath)
        validator = None

    return validator


def build_docs() -> None:
    """Build the MkDocs documentation if source files are present and newer than the existing site output."""
    docs_root = Path("docs")
    env_file = Path(".env")
    mkdocs_config = docs_root / "mkdocs.yml"
    docs_source_dir = docs_root / "mkdocs"
    developers_guide = docs_root / "dev-docs.md"
    pid_guide = docs_root / "pid_guide.md"
    changelog = Path("CHANGELOG.md")
    readme = Path("README.md")
    site_dir = docs_root / "site"

    source_paths = [mkdocs_config, docs_source_dir, developers_guide, pid_guide, changelog, readme]
    freshness_paths = source_paths + ([env_file] if env_file.exists() else [])
    missing_sources = [path for path in source_paths if not path.exists()]
    if missing_sources:
        logger.warning("Skipping MkDocs build because required source path(s) are missing: %s", missing_sources)
        return

    def latest_mtime(paths: list[Path]) -> float:
        latest = 0.0
        for path in paths:
            latest = max(latest, path.stat().st_mtime)
            for p in path.rglob("*"):
                latest = max(latest, p.stat().st_mtime)
        return latest

    # Check if the site output is at least as new as the source files; if so, skip the build
    has_site_output = site_dir.exists() and site_dir.is_dir() and any(site_dir.iterdir())
    if has_site_output:
        newest_source = latest_mtime(freshness_paths)
        newest_output = site_dir.stat().st_mtime
        if newest_source <= newest_output:
            logger.debug("Skipping MkDocs build: docs/site is up to date.")
            return

    try:
        # Load the MkDocs configuration and build the documentation
        os.environ["ROOT_PATH"] = settings.ROOT_PATH
        config = load_config(str(mkdocs_config))
        # Keep build warnings and errors without logging every copied theme asset.
        logging.getLogger("mkdocs").setLevel(logging.INFO)
        logging.getLogger("mkdocs.plugins.mkdocs_macros.util").setLevel(logging.WARNING)
        build.build(config)
    except Exception:
        logger.exception("Error building MkDocs documentation.")
