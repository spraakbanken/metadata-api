"""Macros for MkDocs documentation."""

import os
import re
from pathlib import Path
from typing import Any

DOCS_ROOT = Path(__file__).parent
README_SOURCE = DOCS_ROOT.parent / "README.md"
README_DESTINATION = DOCS_ROOT / "mkdocs" / "README.md"
API_BASE_URL_PATTERN = re.compile(r"https://ws\.spraakbanken\.gu\.se/ws/metadata/v[^/?#\s)\]\\\"']+")
DEVELOPER_DOCUMENTATION_LINE_PATTERN = re.compile(
    r"^For more technical details, see the \[developer documentation\]\([^)]+\)\.\n*",
    re.MULTILINE,
)
API_CALLS_INTRO_LINE_PATTERN = re.compile(r"^Available API calls \(please note that.*\n*", re.MULTILINE)


def define_env(env: Any) -> None:
    """Define environment variables for MkDocs."""
    env.variables["base_url"] = os.getenv("ROOT_PATH", "")


def on_pre_build(config: Any) -> None:
    """Copy the README into the docs source and replace the deployed API base URL."""
    _ = config
    readme = README_SOURCE.read_text(encoding="utf-8")
    rendered_readme = DEVELOPER_DOCUMENTATION_LINE_PATTERN.sub("", readme)
    rendered_readme = API_CALLS_INTRO_LINE_PATTERN.sub("", rendered_readme)
    rendered_readme = API_BASE_URL_PATTERN.sub("{{ base_url }}", rendered_readme)

    if not README_DESTINATION.exists() or README_DESTINATION.read_text(encoding="utf-8") != rendered_readme:
        README_DESTINATION.write_text(rendered_readme, encoding="utf-8")
