"""Shared constants for PID/DOI generation."""

from pathlib import Path

YAML_DIR = Path(__file__).parent.resolve().parent / "metadata" / "yaml"
DOI_KEY = "doi"  # DOI = Digital Object Identifier

# DMS (DataCite Metadata Schema) constants
DMS_URL = "https://api.datacite.org/dois"
DMS_HEADERS = {
    "content-type": "application/json",
    "User-agent": "GenPids/1.0 (https://spraakbanken.gu.se; mailto:sb-webb@svenska.gu.se)",
}
DMS_PREFIX = "10.23695"
DMS_REPOID = "SND.SPRKB"
DMS_CREATOR_NAME = "Språkbanken Text"
DMS_CREATOR_ROR = "https://ror.org/03xfh2n14"
DMS_TARGET_RESOURCE_PREFIX = "https://spraakbanken.gu.se/resurser/"
DMS_TARGET_ANALYSIS_PREFIX = "https://spraakbanken.gu.se/analyser/"
DMS_RESOURCE_TYPE_DATASET = "Dataset"
DMS_RESOURCE_TYPE_ANALYSIS = "Workflow"
DMS_RESOURCE_TYPE_COLLECTION = "Collection"
DMS_SLUG = "slug"  # Språkbanken Texts resource ID ("slug") type
DMS_HANDLE = "handle"
DMS_LANG_ENG = "en"
DMS_LANG_SWE = "sv"
DMS_LANG_MUL = "mul"
DMS_TITLE_EXAMPLE_SWE = "Exempel (in English)"
DMS_TITLE_EXAMPLE_ENG = "Example"
DMS_LICENSE_SCHEME_URI = "https://spdx.org/licenses/"
DMS_LICENSE_SCHEME_ID = "SPDX"
DMS_LICENSE_OTHER = "LicenseRef-Other"

DMS_RELATION_TYPE_ISPARTOF = "IsPartOf"
DMS_RELATION_TYPE_HASPART = "HasPart"
DMS_RELATION_TYPE_ISOBSOLETEDBY = "IsObsoletedBy"
DMS_RELATION_TYPE_OBSOLETES = "Obsoletes"

# Datacite API response codes and settings
RESPONSE_OK = 200
RESPONSE_CREATED = 201
DATACITE_RATE_LIMIT = 298
DATACITE_RATE_LIMIT_TIMEOUT = 60 * 5
DATACITE_REQUEST_TIMEOUT = 30
