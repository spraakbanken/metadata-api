# Changelog

All notable API changes will be documented in this file. The format is based on [Keep a
Changelog](https://keepachangelog.com/en/1.0.0/).

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

### Removed

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

[3.1]: https://github.com/spraakbanken/metadata-api/compare/v3.0...v3.1
[3.0]: https://github.com/spraakbanken/metadata-api/compare/v2.0...v3.0
[2.0]: https://github.com/spraakbanken/metadata-api/releases/tag/v2.0
