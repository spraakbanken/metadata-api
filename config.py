"""General configuration."""

# Flask settings
DEBUG = False

CORPORA_FILE = "corpora.json"
LEXICONS_FILE = "lexicons.json"
MODELS_FILE = "models.json"
RESOURCE_TEXTS_FILE = "resource-texts.json"

NO_CACHE = False  # Set to True to disable caching with memcached
MEMCACHED_HOST = "localhost"
MEMCACHED_PORT = 11211
