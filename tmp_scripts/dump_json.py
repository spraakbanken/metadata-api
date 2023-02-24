"""Get json metadata from SB's metadata API and save it (if it does not exist already)."""

import requests
from pathlib import Path
import json

JSON_PATH = "json"
URL = "https://ws.spraakbanken.gu.se/ws/metadata/"

r = requests.get(URL)
jsonresponse = r.json()

for resources in jsonresponse.values():
    for resource in resources:
        rtype = resource.get("type")
        rid = resource.get("id")
        metadata_path = Path(JSON_PATH) / rtype / (rid + ".json")
        if not metadata_path.is_file() and not resource.get("collection"):

            # Remove download info (is added automatically)
            for d in resource.get("downloads", []):
                d.pop("size", None)
                d.pop("last-modified", None)

            # Remove has_description and get description instead
            has_desc = resource.get("has_description")
            resource.pop("has_description", None)
            if has_desc:
                rurl = URL + f"?resource={rid}"
                try:
                    res = requests.get(rurl).json()
                    # print(res)
                except Exception as e:
                    print(f"Failed to get long description from {rid} ({rurl}). Aborting.")
                    continue
                description_sv = res.get("long_description_sv")
                if description_sv:
                    resource["long_description_sv"] = description_sv
                description_en = res.get("long_description_en")
                if description_en:
                    resource["long_description_en"] = description_en

            # Save json
            dump = json.dumps(resource, indent=4, ensure_ascii=False)
            with open(metadata_path, "w") as f:
                f.write(dump)
                print(f"written {metadata_path}")
