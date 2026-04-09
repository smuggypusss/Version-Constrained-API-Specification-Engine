from __future__ import annotations

import logging

from src.providers.base import ApiIndex, DocSource, EcosystemProvider, ResolvedDependency

logger = logging.getLogger(__name__)


class DocumentationRetriever:

    def __init__(self, providers: list[EcosystemProvider]) -> None:
        ...

    async def retrieve(self, dependency: ResolvedDependency) -> ApiIndex:
        """
        Fetch documentation for a resolved dependency.
        Sources are ranked by reliability. Returns the first successful fetch.
        Raises on total failure after exhausting all sources.
        """
        ...

    async def _fetch_from_source(self, source: DocSource) -> ApiIndex | None:
        ...
