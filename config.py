"""General configuration."""

# Flask settings
DEBUG = False

# Paths relative to 'static' directory
CORPORA_FILE = "corpus.json"
LEXICONS_FILE = "lexicon.json"
MODELS_FILE = "model.json"
ANALYSES_FILE = "analysis.json"
UTILITIES_FILE = "utility.json"
RESOURCE_TEXTS_FILE = "resource-texts.json"
SCHEMA_FILE = "../../metadata/schema/metadata.json"

NO_CACHE = False  # Set to True to disable caching with memcached
MEMCACHED_HOST = "localhost"
MEMCACHED_PORT = 11211
