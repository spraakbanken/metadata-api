"""Asynchronous tasks using Celery."""

import importlib.util
import io
import logging
import sys
from pathlib import Path
from typing import Any

from celery import Celery
from git import Repo

from . import utils
from .parse_yaml import logger as parse_yaml_logger
from .parse_yaml import process_resources


def load_config() -> dict:
    """Load configuration from config_default.py and config.py."""

    def load_module_from_path(module_name: str, file_path: Path) -> Any:
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Could not load spec or loader for {file_path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        return module

    config = {}

    # Load config_default.py
    default_config_path = Path(__file__).parent.parent / "config_default.py"
    config_default = load_module_from_path("config_default", default_config_path)
    config.update({k: v for k, v in vars(config_default).items() if k.isupper()})

    # Load config.py if it exists
    local_config_path = Path(__file__).parent.parent / "config.py"
    if local_config_path.exists():
        config_local = load_module_from_path("config", local_config_path)
        config.update({k: v for k, v in vars(config_local).items() if k.isupper()})

    return config


config = load_config()
logger = logging.getLogger()
app = Celery("metadata_api", broker=config["CELERY_BROKER_URL"])


@app.task
def renew_cache_task(
    request_method: str,
    resource_paths: list | None,
    static_path: str,
    debug: bool,
    offline: bool,
    payload: Any | None = None,
) -> bool:
    """Renew the cache by re-parsing YAML files and updating the cache.

    Args:
        request_method: HTTP method of the request that triggered the task.
        resource_paths: Path to specific resources to parse and update (<resource_type/resource_id>).
        static_path: Path to the static folder.
        debug: Print debug info while parsing YAML files.
        offline: Skip getting file info for downloadables when parsing YAML files.
        payload: payload from the GitHub webhook.

    Returns:
        Whether the cache renewal was successful.
    """
    logger.info("Starting cache renewal task.")

    # Update config with static_path from argument
    config["STATIC"] = Path(static_path)

    errors = []
    warnings = []
    info = []

    # Pull changes from GitHub before parsing YAML files
    try:
        repo = Repo(config["METADATA_DIR"])
        repo.remotes.origin.pull()
        logger.debug("Successfully pulled latest changes from GitHub (dir: %s)", repo.working_dir)
    except Exception as e:
        logger.exception("Failed to pull changes from GitHub")
        msg = f"Failed to pull changes from GitHub: {e}"
        errors.append(msg)
        utils.send_to_slack(msg, config.get("SLACK_WEBHOOK", ""))
        return False

    # Parse POST request payload from GitHub webhook
    if request_method == "POST":
        logger.info("Parsing POST request from GitHub webhook for changed files.")
        try:
            logger.debug("GitHub payload: %s", payload)
            if payload:
                # Check if the webhook was triggered on the main branch
                if payload.get("ref", "") != "refs/heads/main":
                    msg = "GitHub webhook triggered, but not on main branch. Nothing to do."
                    logger.info(msg)
                    return True

                # Check if payload contains a list of changed files
                changed_files = []
                git_commits = payload.get("commits", [])
                if not git_commits:
                    msg = f"No commits detected in payload.\nPayload:\n{payload}"
                    logger.error(msg)
                    utils.send_to_slack(msg, config.get("SLACK_WEBHOOK", ""))
                    return False

                for commit in git_commits:
                    changed_files.extend(commit.get("added", []))
                    changed_files.extend(commit.get("modified", []))
                    changed_files.extend(commit.get("removed", []))

                # If too many files were changed, GitHub will not provide a complete list. Update all data in this case.
                file_limit = config["GITHUB_FILE_LIMIT"]
                if len(changed_files) > file_limit:
                    resource_paths = None
                # Format paths (strip first component and file ending) to create input for process_resources
                else:
                    resource_paths = []
                    for p in changed_files:
                        # Only process resource metadata YAML files
                        if Path(p).parts[0] == "yaml" and Path(p).suffix == ".yaml":
                            resource_paths.append(str(Path(*Path(p).parts[1:-1]) / Path(p).stem))

        except Exception as e:
            msg = f"Error parsing GitHub payload: {e}.\nPayload:\n{payload}"
            logger.exception(msg)
            utils.send_to_slack(msg, config.get("SLACK_WEBHOOK", ""))
            return False

    # Create a string buffer to capture logs from process_resources
    log_capture_string = io.StringIO()
    log_handler = logging.StreamHandler(log_capture_string)
    log_handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    parse_yaml_logger.addHandler(log_handler)

    try:
        logger.info("Calling 'process_resources'...")
        # Update data and rebuild all JSON files (reprocess all data if resource_paths is None)
        process_resources(
            resource_paths=resource_paths, config_obj=config, validate=True, debug=debug, offline=offline
        )
        logger.info("Cache renewal task: process_resources completed.")

        cache_client = None
        if not config.get("NO_CACHE") and config.get("cache_client") is not None:
            cache_client = config["cache_client"]
            cache_client.flush_all()
        # Reload resources and resource texts to populate cache
        utils.load_resources(config["RESOURCES"], config["STATIC"], cache_client=cache_client)
        utils.load_json(
            config["STATIC"] / config["RESOURCE_TEXTS_FILE"], prefix="res_descr", cache_client=cache_client
        )
        utils.load_json(config["STATIC"] / config["COLLECTIONS_FILE"], cache_client=cache_client)
        success = True

    except Exception as e:
        logger.exception("Error during cache renewal")
        success = False
        errors = [str(e)]

    # Get the process_resources logs from the string buffer
    log_messages = log_capture_string.getvalue().splitlines()
    log_capture_string.close()
    parse_yaml_logger.removeHandler(log_handler)

    # Sort log messages into errors, warnings, and info/other
    for message in log_messages:
        if message.startswith(("ERROR", "CRITICAL")):
            errors.append(message)
        elif message.startswith("WARNING"):
            warnings.append(message)
        else:
            info.append(message)

    if errors or warnings:
        logger.warning("Cache renewal completed with errors or warnings:\n%s", "\n".join(errors + warnings))
        utils.send_to_slack(
            "Cache renewal completed.\n" + "\n".join(errors + warnings), config.get("SLACK_WEBHOOK", "")
        )

    logger.info("Cache renewal task finished successfully.")
    return success
