"""Tests for parse_yaml module."""

import logging
from collections import defaultdict
from pathlib import Path

import pytest

from metadata_api.parse_yaml import _get_validator, _process_yaml_file  # noqa: PLC2701
from metadata_api.settings import settings

YAML_CONTENT: str = """
name:
    swe: temp
license: MIT license
type: utility
"""


def test__process_yaml_file_fails_with_bad_instance(caplog: pytest.LogCaptureFixture) -> None:
    """Test that _process_yaml_file logs an error when the license is not valid."""
    filepath = Path("tests/assets/gen/tempfile.yaml")
    filepath.write_text(YAML_CONTENT, encoding="utf-8")
    resource_texts = defaultdict(dict)
    validator = _get_validator(settings.METADATA_DIR / settings.SCHEMA_FILE)
    assert validator is not None
    collection_mappings = {}
    localizations = {}
    license_info = {}
    with caplog.at_level(logging.INFO):
        _process_yaml_file(
            filepath, resource_texts, collection_mappings, validator, localizations, license_info, offline=True
        )
    assert '"MIT license" is not one of' in caplog.text
