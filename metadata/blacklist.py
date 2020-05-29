"""Resources that should not appear in the API."""

BLACKLIST = {
    "corpora": [],
    "lexicons": [
        "blisschar",  # detta är en del av Bliss-lexikonet, och bör inte publiceras separat
        "blissword",  # detta är en del av Bliss-lexikonet, och bör inte publiceras separat
    ]
}
