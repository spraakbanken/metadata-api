"""Utility functions for dumping YAML files with preserved formatting."""


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

    def increase_indent(self, flow: bool = False, indentless: bool = False) -> None:  # noqa: ARG002
        """Increase the indentation level."""
        return super().increase_indent(flow, indentless=False)


yaml.add_representer(str, str_presenter)
IndentDumper.add_representer(str, str_presenter)
