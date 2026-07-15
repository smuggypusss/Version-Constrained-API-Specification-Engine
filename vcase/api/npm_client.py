from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)

NPM_REGISTRY_BASE_URL = "https://registry.npmjs.org"
REQUEST_TIMEOUT_SECONDS = 10


class NpmClient:

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def get_package_info(self, package: str, version: str) -> dict:
        """Fetch package metadata from npm registry. Raises on non-200 response."""
        url = f"{NPM_REGISTRY_BASE_URL}/{package}/{version}"
        response = await self._client.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
        response.raise_for_status()
        return response.json()

    async def get_latest_version(self, package: str) -> str:
        """Return the latest published version string for a package."""
        url = f"{NPM_REGISTRY_BASE_URL}/{package}"
        response = await self._client.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
        response.raise_for_status()
        data = response.json()
        version = data.get("dist-tags", {}).get("latest", "")
        if not version:
            logger.warning("Could not determine latest version for npm package %s", package)
        return version
