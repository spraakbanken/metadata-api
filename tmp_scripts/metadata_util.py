"""Metadata utilities

The idea is to add small reusable utility functions for working with metadata here.

Changes:
2024-05-29 Creation
2024-05-29 Added export_resources_to_tsv() (Staffan)
2024-06-14 Added update_field_updated() (Staffan)

"""
import argparse
import datetime
import requests
import yaml

from pathlib import Path


#import json
#import netrc
#import re
#import sys
#import traceback
#import urllib.parse

#from collections import defaultdict
#from requests.auth import HTTPBasicAuth



# Instantiate command line arg parser
parser = argparse.ArgumentParser(prog = "metadata_util",
                                 description="Metadata utilities - small functions for working with metadata.")
parser.add_argument("--export", 
                    action="store_true", 
                    help="Export some fields from all metadata into a tsv")

parser.add_argument("--updated", 
                    action="store_true", 
                    help="Update field updated based on source file date")


"""Export"""


def get_key_value(dictionary: dict, key: str, key2: str = None) -> str:
    """Return key value from dictionary, else empty string."""
    if (key2 == None):
        value = dictionary.get(key, "")
        return value if value else ""
    else:
        if key in dictionary:
            value = get_key_value(dictionary[key], key2) 
            return value if value else ""
        else:
            return ""

def export_resources_to_tsv():
    """Utility function to export selected info of all resources

    """
    DMS_TARGET_URL_PREFIX = "https://spraakbanken.gu.se/resurser/"

    file_export = Path("../metadata/export.tsv")
    EXPORT_TAB = "\t"
    EXPORT_NEWLINE = "\n"
    with file_export.open("w") as file_csv:
        for filepath in sorted(YAML_DIR.glob("**/*.yaml")):
            res_id = filepath.stem
            with filepath.open(encoding="utf-8") as file_yaml:
                res = yaml.safe_load(file_yaml)
                if get_key_value(res, "collection") == True:
                    res_type = "collection"
                else:
                    res_type = get_key_value(res, "type")
                file_csv.write(get_key_value(res, "name", "swe")
                                        + EXPORT_TAB + get_key_value(res, "name", "eng")
                                        + EXPORT_TAB + res_type
                                        + EXPORT_TAB + DMS_TARGET_URL_PREFIX + res_id
                                        + EXPORT_NEWLINE)


"""Updated"""


def str_presenter(dumper, data):
    """Configure yaml package for dumping multiline strings (for preserving format).

    # https://github.com/yaml/pyyaml/issues/240
    # https://pythonhint.com/post/9957829820118202/yamldump-adding-unwanted-newlines-in-multiline-strings
    # Ref: https://stackoverflow.com/questions/8640959/how-can-i-control-what-scalar-form-pyyaml-uses-for-my-data
    """
    if data.count("\n") > 0:  # check for multiline string
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)

yaml.add_representer(str, str_presenter)
yaml.representer.SafeRepresenter.add_representer(str, str_presenter)

class IndentDumper(yaml.Dumper):
    """Indent list items (for preserving format).

    https://reorx.com/blog/python-yaml-tips/#enhance-list-indentation-dump
    """
    def increase_indent(self, flow=False, indentless=False):
        return super(IndentDumper, self).increase_indent(flow, False)

def get_download_date_(url, name):
    """Check headers of file from url and return the last modified date."""
    res = requests.head(url)
    date = res.headers.get("Last-Modified")

    if date:
        date = datetime.date.strptime(date, "%a, %d %b %Y %H:%M:%S %Z") #.strftime("%Y-%m-%d")
    if res.status_code == 404:
        print(f"Error: Could not find downloadable for '{name}': {url}")
    return date

YAML_DIR = Path("../metadata/yaml")

def update_field_updated():
    """Update field updated based on source file date

    Preferably run locally on checked out files.

    Add wew field 'updated'.
    The field needs to be initialized.
    Use modification date of data file
    If only statistics file exists, use that.
    If several files are included, use the most recent.
    """
    for filepath in sorted(YAML_DIR.glob("**/*.yaml")):
        res_id = filepath.stem
        with filepath.open(mode = "r+", encoding="utf-8") as file_yaml:
            res = yaml.safe_load(file_yaml)
            #res_type = res.get("type")
            updated = res.get("updated", None) # date
            if not updated:
                # get date of last updated download/source file
                for d in res.get("downloads", []):
                    url = d.get("url")
                    if url and not ("updated" in d):
                        date = get_download_date_(url, res_id) # date
                        if date:
                            if not updated:
                                updated = date
                            elif date > updated:
                                updated = date
        if updated:
            with filepath.open(mode = "r+", encoding="utf-8") as file_yaml:
                # find out if last char is \n
                while True:
                    char = file_yaml.read(1)
                    if not char:
                        break
                    last_char_is_newline = (char == '\n')
                print(f"Info: '{res_id}': {updated}")
                if last_char_is_newline:
                    file_yaml.write(f"updated: {updated}\n")
                else:
                    print(res_id)
                    file_yaml.write(f"\nupdated: {updated}\n")
    """
        Version where we tried to write complete YAML
        
        for filepath in sorted(YAML_DIR.glob("**/*.yaml")):
        res_id = filepath.stem
        with filepath.open(mode = "r+", encoding="utf-8") as file_yaml:
            res = yaml.safe_load(file_yaml)
            #res_type = res.get("type")
            updated = res.get("updated", None) # date
            if type(updated) is datetime.date:
                updated = updated.strftime("%Y-%m-%d")
            # get date of last updated download/source file
            for d in res.get("downloads", []):
                url = d.get("url")
                if url and not ("updated" in d):
                    date = get_download_date_(url, res_id)
                    if date:
                        if not updated:
                            updated = date
                        elif date > updated:
                            updated = date
            if updated:
                res["updated"] = datetime.datetime.strptime(updated, "%Y-%m-%d").date()
                print(f"Info: '{res_id}': {updated}")
                file_yaml.seek(0)
                file_yaml.truncate(0)
                yaml.dump(
                    res,
                    file_yaml,
                    Dumper=IndentDumper, 
                    sort_keys=False, 
                    default_flow_style=False, 
                    allow_unicode=True
                )
    """


def main(args) -> None:
    if args.export:
        export_resources_to_tsv()
    if args.updated:
        update_field_updated()

if __name__ == "__main__":
    main(args = parser.parse_args())