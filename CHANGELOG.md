# Changelog

All notable API changes will be documented in this file. The format is based on [Keep a
Changelog](https://keepachangelog.com/en/1.0.0/).

## [unreleased]


## [3.2.0] - 2025-12-03

### Added

- Added an `update` argument to the `gen_pids.sh` script to force updates of all Datacite metadata.
- Added proper license information to Datacite metadata.
- Added `/redoc` route for API documentation with ReDoc.
- Added `/docs` route for API documentation with Swagger UI.

### Changed

- Flask is replaced with FastAPI as the web framework and the app is run asynchronously.
- Minimal Python version is now 3.11.
- The app is now run with `uvicorn` instead of `gunicorn`.
- Cache-renewal is now done in a background task with Celery, using Redis as broker.
- Change preferred installation method to use `uv` for dependency management.
- `gen_pids.py` now uses logging instead of print statements.
- Moved some documentation from README.md to docs/dev-docs.md.
- Slightly improved caching logic.

### Deprecated

- The `/corpora`, `/lexicons`, `/models`, `/analyses`, `/utilities` and `/collections` routes are deprecated and will be
  removed in a future version. Use the main `/` route with the `resource` parameter instead.
- The `/doc` route serving the OpenAPI documentation in YAML format is deprecated and will be removed in a future
  version. Use `/openapi.json` instead.

### Fixed

- Cache-renewal is only triggered when changes are detected in the main branch of the metadata repo (instead of all
  branches).
- Fixed bug in `gen_pids.py` that caused emtpy resource sized.
- Fixed Pylance type warnings.

## [3.1] - 2025-02-28

### Added

- Better error handling and logging for 404 errors.
- Added documentation about caching.
- Added possibility to send error messages to a Slack channel. The URL can be configured with the `SLACK_WEBHOOK`
  variable.
- Added a shell script for extracting the version number from `__init__.py` and changing references to the API version
  in `README.md`.
- When running a test server, the port can now be supplied as an argument to `run.py`.

### Fixed

- The `/schema` route now correctly reflects the schema for the resource data returned by the API.
- Fixed bug that caused errors in logging.
- Do not delete the app logs during log rotation in `gen_pids.sh`.
- Fixed bug in `/renew-cache` that caused attempts to process non-metadata files.

## [3.0] - 2025-02-25

### Added

- It is now possible to use a custom config (`config.py`) for overriding values defined in the default config.
- Proper logging and better error handling.

### Changed

- Integrated `parse_yaml.py` into the API. YAML files are now parsed when calling the `/renew-cache` route.
- It is now possible to perform a cache refresh with specific updated/deleted resources by supplying the
  `resource-paths` parameter to `/renew-cache`.
- The format for the resource data has been updated. A json schema will be available soon.
- The API documentation is now served as JSON instead of YAML (by `/doc`).
- It is now possible to add a new resource type by adding it to the `RESOURCES` dictionary in the config file.

## [2.0] - 2025-02-14

This version has been developed over a long period and is therefore incomplete. It only contains the latest changes.
Please refer to the git commit log for more information.

### Added

- Added a route for creating a bibtex citation for a specific resource: `/bibtex?resource=[some-id]`
- Added a route for lising analyses: `/analyses`
- Added a route for listing utilities: `/utilities`
- Added a script for generating PIDs and registering resources at Datacite.

[unreleased]: https://github.com/spraakbanken/metadata-api/compare/v3.2.0...dev
[3.2.0]: https://github.com/spraakbanken/metadata-api/releases/tag/v3.2.0
[3.1]: https://github.com/spraakbanken/metadata-api/releases/tag/v3.1
[3.0]: https://github.com/spraakbanken/metadata-api/releases/tag/v3.0
[2.0]: https://github.com/spraakbanken/metadata-api/releases/tag/v2.0
