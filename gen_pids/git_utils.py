"""Git utilities for committing metadata changes."""

import logging

from git import Actor, GitCommandError, Repo

from gen_pids.settings import GIT_AUTHOR_EMAIL, GIT_AUTHOR_NAME, YAML_REPO_ROOT

logger = logging.getLogger("gen_pids")


def commit_metadata_changes() -> None:
    """Stage, commit, and push metadata changes using GitPython."""
    # Open the git repository
    try:
        repo = Repo(YAML_REPO_ROOT)
    except Exception:
        logger.exception("Failed to open git repo at %s", YAML_REPO_ROOT)
        return

    # Stage all changes
    try:
        repo.git.add("--all", "metadata/yaml")
    except GitCommandError:
        logger.exception("Git add failed for metadata/yaml")
        return

    # Check if there are any changes to commit
    try:
        if not repo.index.diff("HEAD"):
            logger.debug("No metadata changes to commit.")
            return
    except Exception:
        logger.exception("Failed to check git status.")
        return

    # Commit changes
    author = Actor(GIT_AUTHOR_NAME, GIT_AUTHOR_EMAIL)
    try:
        repo.index.commit("automatically added PIDs through gen_pids.py", author=author, committer=author)
    except GitCommandError:
        logger.exception("Git commit failed")
        return

    # Push changes
    try:
        push_results = repo.remotes.origin.push()
    except Exception:
        logger.exception("Git push failed")
        return

    # Log push results
    for result in push_results:
        if result.flags & result.ERROR:
            logger.error("Git push error: %s", result.summary)
        else:
            logger.info("Git push: %s", result.summary)
