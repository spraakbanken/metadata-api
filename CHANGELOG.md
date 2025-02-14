# Changelog

All notable API changes will be documented in this file. The format is based on [Keep a
Changelog](https://keepachangelog.com/en/1.0.0/).

## [2.0] - 2025-02-14

This version has been developed over a long period and is therefore incomplete. It only contains the latest changes.
Please refer to the git commit log for more information.

### Added

- Added a route for creating a bibtex citation for a specific resource: `/bibtex?resource=[some-id]`
- Added a route for lising analyses: `/analyses`
- Added a route for listing utilities: `/utilities`
- Added a route for listing all existing resource IDs in the database: `/list_ids`
- Added a route for checking if a resource ID already exists in the database: `check-id-availability?id=my-resource`
- Added a script for generating PIDs and registering resources at Datacite.

[2.0]: https://github.com/spraakbanken/metadata-api/releases/tag/v2.0
