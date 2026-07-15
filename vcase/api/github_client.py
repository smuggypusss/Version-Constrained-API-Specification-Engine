from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)

GITHUB_API_BASE_URL = "https://api.github.com"
REQUEST_TIMEOUT_SECONDS = 10


class GithubClient:

    def __init__(self, client: httpx.AsyncClient, api_token: str | None = None) -> None:
        ...

    async def get_release_notes(self, owner: str, repo: str, tag: str) -> str:
        """Return release notes markdown for a given tag."""
        ...

    async def get_readme(self, owner: str, repo: str, ref: str) -> str:
        """Return the README content for a given ref (tag or branch)."""
        ...
