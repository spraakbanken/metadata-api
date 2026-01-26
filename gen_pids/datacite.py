"""Lightweight DataCite client wrapper."""

from __future__ import annotations

import logging
import netrc
import sys
import time
import traceback
from typing import Any

import requests
from requests.auth import HTTPBasicAuth

from gen_pids.settings import (
    DATACITE_RATE_LIMIT,
    DATACITE_RATE_LIMIT_TIMEOUT,
    DATACITE_REQUEST_TIMEOUT,
    DMS_HEADERS,
    DMS_REPOID,
    DMS_SLUG,
    DMS_URL,
)


class DataCiteClient:
    """Thin wrapper around DataCite REST API calls."""

    def __init__(
        self,
        user: str,
        password: str,
        logger: logging.Logger | None = None,
    ) -> None:
        """Initialize DataCite client."""
        self.auth = HTTPBasicAuth(user, password)
        self.rate_limit = DATACITE_RATE_LIMIT
        self.rate_limit_timeout = DATACITE_RATE_LIMIT_TIMEOUT
        self.timeout = DATACITE_REQUEST_TIMEOUT
        self.logger = logger or logging.getLogger("gen_pids")
        self.calls = 0

    def _sleep_if_rate_limited(self) -> None:
        if self.rate_limit and self.calls >= self.rate_limit:
            self.logger.debug("Rate limit reached, sleeping for %s seconds", self.rate_limit_timeout)
            time.sleep(self.rate_limit_timeout)
            self.calls = 0

    def _request(self, method: str, url: str, **kwargs: Any) -> requests.Response:
        self._sleep_if_rate_limited()
        if self.timeout is not None:
            kwargs.setdefault("timeout", self.timeout)
        response = requests.request(method, url, **kwargs)
        self.calls += 1
        return response

    def get_doi_by_slug(self, res_id: str) -> requests.Response:
        """Lookup a DOI using the resource slug."""
        params = {
            "client-id": DMS_REPOID,
            "query": f"identifiers.identifier:{res_id} AND identifiers.identifierType:{DMS_SLUG}",
            "detail": "true",
        }
        return self._request("get", DMS_URL, params=params)

    def get_record(self, doi: str) -> requests.Response:
        """Fetch a DOI record."""
        return self._request("get", f"{DMS_URL}/{doi}")

    def create_doi(self, data_json: dict) -> requests.Response:
        """Create a new DOI."""
        return self._request("post", DMS_URL, json=data_json, headers=DMS_HEADERS, auth=self.auth)

    def update_doi(self, doi: str, data_json: dict) -> requests.Response:
        """Update an existing DOI."""
        url = f"{DMS_URL}/{doi}"
        return self._request("put", url, json=data_json, headers=DMS_HEADERS, auth=self.auth)


def build_datacite_client(logger: logging.Logger | None = None) -> DataCiteClient:
    """Build a DataCite client from netrc credentials."""
    log = logger or logging.getLogger("gen_pids")
    try:
        auth = netrc.netrc().authenticators("datacite.org")
        if auth is None:
            raise ValueError("No authenticators found for datacite.org in netrc file.")
        dms_auth_user, _dms_auth_account, dms_auth_password = auth
    except Exception:
        log.critical("Failed to retrieve DataCite authenticators from netrc. Exiting.")
        log.critical(traceback.format_exc())
        # TODO: when rewriting the API (https://github.com/spraakbanken/metadata-api/issues/26) this file might no longer
        # be a script but instead a module which is imported. Then we don't want to exit the whole program here, but
        # rather raise an exception that can be caught by the caller.
        sys.exit()

    return DataCiteClient(
        dms_auth_user,
        dms_auth_password,
        logger=log,
    )
