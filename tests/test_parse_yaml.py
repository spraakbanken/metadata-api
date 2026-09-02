"""Tests for parse_yaml module."""

import logging
from collections import defaultdict
from pathlib import Path

import pytest

from metadata_api.parse_yaml import _process_yaml_file  # ruff: ignore[import-private-name]
from metadata_api.settings import settings
from metadata_api.utils import get_schema_validator

YAML_CONTENT: str = """
name:
    swe: temp
license: MIT license
type: utility
origin: sbx
"""

YAML_WITH_EMPTY_LANGUAGE: str = """
name:
    swe: temp
license: MIT license
type: utility
languages:
  - code: ''
    name:
      swe: ''
      eng: ''
  - code: sv-FI
    name:
      swe: finlandssvenska
      eng: Finland Swedish
origin: sbx
"""


def test__process_yaml_file_fails_with_bad_instance(caplog: pytest.LogCaptureFixture) -> None:
    """Test that _process_yaml_file logs an error when the license is not valid."""
    filepath = Path("tests/assets/gen/tempfile.yaml")
    filepath.write_text(YAML_CONTENT, encoding="utf-8")
    resource_texts = defaultdict(dict)
    validator = get_schema_validator(settings.METADATA_DIR / settings.SCHEMA_FILE)
    assert validator is not None
    collection_mappings = {}
    localizations = {}
    license_info = {}
    with caplog.at_level(logging.INFO):
        _process_yaml_file(
            filepath, resource_texts, collection_mappings, validator, localizations, license_info, offline=True
        )
    assert '"MIT license" is not one of' in caplog.text


def test__process_yaml_file_removes_empty_language_entries() -> None:
    """Test that empty language objects are removed from the parsed resource."""
    filepath = Path("tests/assets/gen/tempfile.yaml")
    filepath.write_text(YAML_WITH_EMPTY_LANGUAGE, encoding="utf-8")
    resource_texts = defaultdict(dict)
    collection_mappings = {}
    localizations = {}
    license_info = {}

    resource, success = _process_yaml_file(
        filepath,
        resource_texts,
        collection_mappings,
        schema_validator=None,
        localizations=localizations,
        license_info=license_info,
        offline=True,
    )

    assert success is True
    assert resource["languages"] == [{"code": "sv-FI", "name": {"swe": "finlandssvenska", "eng": "Finland Swedish"}}]
