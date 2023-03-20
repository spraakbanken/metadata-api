"""General configuration."""

# Flask settings
DEBUG = False

CORPORA_FILE = "corpus.json"
LEXICONS_FILE = "lexicon.json"
MODELS_FILE = "model.json"
RESOURCE_TEXTS_FILE = "resource-texts.json"

HIDE_FROM_LISTING = ["contact_info", "size", "successors"]

NO_CACHE = False  # Set to True to disable caching with memcached
MEMCACHED_HOST = "localhost"
MEMCACHED_PORT = 11211
