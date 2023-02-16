"""Resources that should not appear in the API."""

BLACKLIST = {
    "corpus": [],
    "lexicon": [
        "blissword",  # detta är en del av Bliss-lexikonet, och bör inte publiceras separat
        "blisschar",  # detta är en del av Bliss-lexikonet, och bör inte publiceras separat
    ],
    "model": [],
    "collection": [],
}
