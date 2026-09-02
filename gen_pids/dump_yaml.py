"""Utility functions for dumping YAML files with preserved formatting."""

from pathlib import Path
from typing import Any

import yaml


def str_presenter(dumper: yaml.Dumper, data: str) -> yaml.ScalarNode:
    """Configure yaml package for dumping multiline strings (for preserving format).

    # https://github.com/yaml/pyyaml/issues/240
    # https://pythonhint.com/post/9957829820118202/yamldump-adding-unwanted-newlines-in-multiline-strings
    # Ref: https://stackoverflow.com/questions/8640959/how-can-i-control-what-scalar-form-pyyaml-uses-for-my-data
    """
    if data.count("\n") > 0:  # check for multiline string
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)


class IndentDumper(yaml.Dumper):
    """Indent list items (for preserving format).

    https://reorx.com/blog/python-yaml-tips/#enhance-list-indentation-dump
    """

    def increase_indent(self, flow: bool = False, indentless: bool = False) -> None:  # ruff: ignore[unused-method-argument]
        """Increase the indentation level."""
        return super().increase_indent(flow, indentless=False)


yaml.add_representer(str, str_presenter)
IndentDumper.add_representer(str, str_presenter)


def read_header_comment(filepath: Path) -> str:
    """Return the leading comment block (and blank lines) from a YAML file."""
    header_lines: list[str] = []
    saw_comment = False
    try:
        file_yaml = filepath.open(encoding="utf-8")
    except Exception:
        return ""

    with file_yaml:
        for line in file_yaml:
            stripped = line.lstrip()
            if stripped.startswith("#"):
                header_lines.append(line.rstrip("\n"))
                saw_comment = True
                continue
            if not stripped:
                if saw_comment:
                    header_lines.append(line.rstrip("\n"))
                continue
            break

    if not saw_comment:
        return ""

    # Remove trailing blank lines
    while header_lines and not header_lines[-1].strip():
        header_lines.pop()

    return "\n".join(header_lines) + "\n"


def dump_with_header(filepath: Path, data: Any) -> None:
    """Dump YAML with preserved top-of-file comment block."""
    header = read_header_comment(filepath)
    dumped = yaml.dump(
        data,
        Dumper=IndentDumper,
        sort_keys=False,
        allow_unicode=True,
    )
    with filepath.open(mode="w", encoding="utf-8") as file_yaml:
        if header:
            file_yaml.write(header)
        file_yaml.write(dumped)
