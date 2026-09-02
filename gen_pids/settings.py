"""Shared constants for PID/DOI generation."""

from pathlib import Path

LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
LOG_FORMAT = "%(name)s/%(funcName)s: %(levelname)s - %(message)s"

# YAML metadata repository paths
YAML_REPO_ROOT = Path(__file__).resolve().parent.parent / "metadata"
YAML_DIR = YAML_REPO_ROOT / "yaml"

DOI_KEY = "doi"  # DOI = Digital Object Identifier

# DMS repository credentials
DMS_URL = "https://api.datacite.org/dois"
DMS_PREFIX = "10.23695"
DMS_REPOID = "SND.SPRKB"
DMS_AUTH_PASSWORD = ""

# DMS (DataCite Metadata Schema) constants
DMS_HEADERS = {
    "content-type": "application/json",
    "User-agent": "GenPids/1.0 (https://spraakbanken.gu.se; mailto:sb-webb@svenska.gu.se)",
}
DMS_CREATOR_NAME = "Språkbanken"
DMS_CREATOR_ROR = "https://ror.org/05qhvy459"
DMS_TARGET_RESOURCE_PREFIX = "https://spraakbanken.gu.se/resurser/"
DMS_TARGET_ANALYSIS_PREFIX = "https://spraakbanken.gu.se/analyser/"
DMS_RESOURCE_TYPE_DATASET = "Dataset"
DMS_RESOURCE_TYPE_ANALYSIS = "Workflow"
DMS_RESOURCE_TYPE_COLLECTION = "Collection"
DMS_SLUG = "slug"  # Språkbanken's resource ID ("slug") type
DMS_HANDLE = "handle"
DMS_LANG_ENG = "en"
DMS_LANG_SWE = "sv"
DMS_LANG_MUL = "mul"
DMS_TITLE_EXAMPLE_SWE = "Exempel (in English)"
DMS_TITLE_EXAMPLE_ENG = "Example"
DMS_LICENSE_SCHEME_URI = "https://spdx.org/licenses/"
DMS_LICENSE_SCHEME_ID = "SPDX"
DMS_LICENSE_OTHER = "LicenseRef-Other"
DMS_LANGUAGE_SCHEME_URI = "http://lexvo.org/id/iso639-3"

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

# Git settings
GIT_AUTHOR_NAME = "sb-sparv"
GIT_AUTHOR_EMAIL = "38045079+sb-sparv@users.noreply.github.com"
