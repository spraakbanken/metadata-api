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

# Paths relative to the location of this config file
SCHEMA_FILE = "metadata/schema/metadata.json"
YAML_DIR = "metadata/yaml"
LOCALIZATIONS_DIR = "metadata/localizations"

# Logging settings
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"
LOG_DIR = "logs"

# Caching settings
NO_CACHE = False  # Set to True to disable caching with memcached
MEMCACHED_HOST = "localhost"
MEMCACHED_PORT = 11211
