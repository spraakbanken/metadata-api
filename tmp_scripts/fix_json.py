"""Script for changing the json metadata format."""

import json
from pathlib import Path
import yaml


def main():
    path = Path("../yaml")

    for p in path.rglob("**/*.yaml"):
        if "templates" in p:
            continue
        with open(p) as f:
            metadata = yaml.load(f, Loader=yaml.FullLoader)

        for k, v in metadata.get("size", {}).items():
            if not v:
                print(p.stem)
            else:
                metadata["size"][k] = int(v)

        print(f"writing {p}")
        with open(p, "w") as yaml_file:
            dump_pretty(metadata, yaml_file)


def sort_json():
    path = Path("../json")

    for p in path.rglob("**/*.json"):
        with open(p) as f:
            metadata = json.load(f)

        new_metadata = {
            "name": metadata["name"],
            "short_description": metadata["short_description"],
            "type": metadata["type"],
            "trainingdata": metadata.get("trainingdata", False),
            "unlisted": metadata.get("unlisted", False),
            "successors": metadata.get("successors", [])
        }
        metadata.pop("name", "")
        metadata.pop("short_description", "")
        metadata.pop("type", "")
        metadata.pop("trainingdata", "")
        metadata.pop("unlisted", "")
        metadata.pop("successors", "")

        # Only for collections
        if metadata.get("collection"):
            new_metadata["collection"] = metadata.get("collection")
            metadata.pop("collection")
        if metadata.get("hide_resources"):
            new_metadata["hide_resources"] = metadata.get("hide_resources")
            metadata.pop("hide_resources")
        if metadata.get("resources"):
            new_metadata["resources"] = metadata.get("resources")
            metadata.pop("resources")

        new_metadata["language_codes"] = metadata.get("language_codes", [])
        metadata.pop("language_codes", "")

        # Optional (only for languages that don't have a standard language code)
        if metadata.get("languages"):
            new_metadata["languages"] = metadata.get("languages")
            metadata.pop("languages")

        # Not used for collections and models
        if metadata.get("size"):
            new_metadata["size"] = metadata.get("size")
        metadata.pop("size", "")

        new_metadata["in_collections"] = metadata.get("in_collections", [])
        new_metadata["downloads"] = metadata.get("downloads", [])
        new_metadata["interface"] = metadata.get("interface", [])
        new_metadata["contact_info"] = metadata["contact_info"]

        metadata.pop("in_collections", "")
        metadata.pop("downloads", "")
        metadata.pop("interface", "")
        metadata.pop("contact_info", "")

        if metadata.get("description"):
            new_metadata["description"] = metadata.get("description")
            metadata.pop("description")

        # Check if anything is left unprocessed
        if metadata:
            print(metadata)

        print(f"writing {p}")
        with open(p, "w") as f:
            json.dump(new_metadata, f, ensure_ascii=False, indent=2)


def convert2yaml():
    p = Path("../yaml/collection/superlim.yaml")

    # for p in path.rglob("**/*.yaml"):
    with open(p) as f:
        metadata = yaml.load(f, Loader=yaml.FullLoader)
        print(metadata)
        # try:
        #     metadata = yaml.load(f, Loader=yaml.FullLoader)
        # except json.decoder.JSONDecodeError:
        #     print(f"failed to convert {p}")
            # continue

        # print(metadata.get("description", {}).get("eng"))

    print(f"writing {p}")
    with open(p, "w") as yaml_file:
        dump_pretty(metadata, yaml_file)


def dump_pretty(data, path):
    """Dump config YAML to string. (stolen from Sparv)"""
    class IndentDumper(yaml.Dumper):
        """Customized YAML dumper that indents lists."""

        def increase_indent(self, flow=False, indentless=False):
            """Force indentation."""
            return super(IndentDumper, self).increase_indent(flow)

    # Add custom string representer for prettier multiline strings
    def str_representer(dumper, data):
        if len(data.splitlines()) > 1:  # Check for multiline string
            data = '\n'.join([line.rstrip() for line in data.strip().splitlines()])
            return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
        return dumper.represent_scalar("tag:yaml.org,2002:str", data)
    yaml.add_representer(str, str_representer)

    return yaml.dump(data, path, sort_keys=False, allow_unicode=True, Dumper=IndentDumper, indent=2, line_break=None,
                     default_flow_style=False)



if __name__ == "__main__":

    # convert2yaml()

    main()
    # sort_json()
    pass
