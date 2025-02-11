"""General configuration."""

# Flask settings
DEBUG = False

# Resource types and their corresponding data files (relative to 'static' directory)
RESOURCES = {
    "corpora": "corpus.json",
    "lexicons": "lexicon.json",
    "models": "model.json",
    "analyses": "analysis.json",
    "utilities": "utility.json",
}
# Resource texts file (relative to 'static' directory)
RESOURCE_TEXTS_FILE = "resource-texts.json"

# Other paths relative to the location of this config file
SCHEMA_FILE = "metadata/schema/metadata.json"
YAML_DIR = "metadata/yaml"
LOCALIZATIONS_DIR = "metadata/localizations"

NO_CACHE = False  # Set to True to disable caching with memcached
MEMCACHED_HOST = "localhost"
MEMCACHED_PORT = 11211
