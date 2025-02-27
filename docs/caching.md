# Caching

Caching can be used in the API to improve response times. [Memcached](https://memcached.org/) is used for this purpose
and can be configured in `config.py` with the following settings:

```python
# Caching settings
NO_CACHE = False  # Set to True to disable caching with memcached
MEMCACHED_HOST = "localhost"
MEMCACHED_PORT = 11211
```

## What is being cached?

- All data for each resource type as a dictionary (example key: `corpus.json`)
- Data for each resource as a dictionary (example key: `attasidor`)
- Resource descriptions for each resource that has one (example key: `res_descr_attasidor`)

## Cache renewal

Cache renewal can be triggered by calling the `/renew-cache` route. This will do the following:

- Changes from the [metadata repository](https://github.com/spraakbanken/metadata) will be pulled from GitHub to update
  the metadata YAML files.
- Metadata YAML files will be reprocessed (either all of them or just the ones specified by the `resource-paths`
  parameter, or the files that were changed in the last push event, specified by the GitHub webhook call) and the static
  JSON files used by the API will be regenerated.
- If memcached caching is activated, the cache is flushed and repopulated with data from the updated JSON files.
