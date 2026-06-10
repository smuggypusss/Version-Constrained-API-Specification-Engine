from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT_SECONDS = 15


class WebScraper:

    def __init__(self, client: httpx.AsyncClient) -> None:
        ...

    async def fetch_as_markdown(self, url: str) -> str:
        """
        Fetch a URL and return its content as clean markdown.
        Strips navigation, ads, and irrelevant HTML. Raises on failure.
        """
        ...

    def _html_to_markdown(self, html: str) -> str:
        ...
