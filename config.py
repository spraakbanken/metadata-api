"""General configuration."""

# Flask settings
DEBUG = False

# Resource types and their corresponding data files (realtive to 'static' directory)
RESOURCES = {
    "corpora": "corpus.json",
    "lexicons": "lexicon.json",
    "models": "model.json",
    "analyses": "analysis.json",
    "utilities": "utility.json",
}

# Other paths relative to 'static' directory
RESOURCE_TEXTS_FILE = "resource-texts.json"
SCHEMA_FILE = "../../metadata/schema/metadata.json"

NO_CACHE = False  # Set to True to disable caching with memcached
MEMCACHED_HOST = "localhost"
MEMCACHED_PORT = 11211
