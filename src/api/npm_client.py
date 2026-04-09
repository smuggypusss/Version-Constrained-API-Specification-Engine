from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)

NPM_REGISTRY_BASE_URL = "https://registry.npmjs.org"
REQUEST_TIMEOUT_SECONDS = 10


class NpmClient:

    def __init__(self, client: httpx.AsyncClient) -> None:
        ...

    async def get_package_info(self, package: str, version: str) -> dict:
        """Fetch package metadata from npm registry. Raises on non-200 response."""
        ...

    async def get_latest_version(self, package: str) -> str:
        """Return the latest published version string for a package."""
        ...
