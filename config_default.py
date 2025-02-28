"""General configuration."""

# Flask settings
DEBUG = False

# Resource types and their corresponding data files (relative to "static" directory)
RESOURCES = {
    "corpora": "corpus.json",
    "lexicons": "lexicon.json",
    "models": "model.json",
    "analyses": "analysis.json",
    "utilities": "utility.json",
}

# Resource texts file and collections file (relative to "static" directory)
RESOURCE_TEXTS_FILE = "resource-texts.json"
COLLECTIONS_FILE = "collection.json"

# Absolute path to metadata directory (https://github.com/spraakbanken/metadata)
METADATA_DIR = "/home/fksbwww/metadata-api/dev/metadata"
# Paths relative to metadata directory
SCHEMA_FILE = "schema/metadata.json"
YAML_DIR = "yaml"
LOCALIZATIONS_DIR = "localizations"

# Logging settings
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"
LOG_DIR = "logs"

# GitHub limit for modified/added files to list in a webhook payload
GITHUB_FILE_LIMIT = 3000

# Caching settings
NO_CACHE = False  # Set to True to disable caching with memcached
MEMCACHED_HOST = "localhost"
MEMCACHED_PORT = 11211

# Slack incoming webhook URL, used to send error messages to a Slack channel
SLACK_WEBHOOK = ""
