"""Script for changing the json metadata format."""

import json
from pathlib import Path

def main():
    path = Path("../json")

    for p in path.rglob("**/*.json"):
        with open(p) as f:
            metadata = json.load(f)

        new_contact = {}
        contact = metadata.get("contact_info", {})
        firstname = contact["givenName"]
        surname = contact["surname"]
        name = f"{firstname} {surname}"
        if name == "Språkbanken Språkbanken":
            name = "Markus Forsberg"

        contact.pop("surname")
        contact.pop("givenName")

        new_contact["name"] = name
        new_contact["email"] = contact["email"]
        new_contact["affiliation"] = contact["affiliation"]
        contact.pop("email")
        contact.pop("affiliation")

        metadata["contact_info"] = new_contact

        print(f"writing {p}")
        with open(p, "w") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)


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



if __name__ == "__main__":
    pass
    # main()
    # sort_json()
