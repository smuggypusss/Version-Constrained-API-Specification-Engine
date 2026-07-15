from __future__ import annotations

import logging
from pathlib import Path

from vcase.providers.base import ApiIndex, DocSource, EcosystemProvider, ResolvedDependency

logger = logging.getLogger(__name__)


class DocumentationRetriever:

    def __init__(self, providers: list[EcosystemProvider]) -> None:
        self._providers = providers

    async def retrieve(self, dependency: ResolvedDependency) -> ApiIndex:
        """
        Fetch documentation/API signature index for a resolved dependency.
        """
        provider = None
        for p in self._providers:
            class_name = p.__class__.__name__
            if dependency.ecosystem.value == "python" and "Python" in class_name:
                provider = p
                break
            elif dependency.ecosystem.value == "node" and "Node" in class_name:
                provider = p
                break

        if not provider:
            logger.warning(f"No matching provider found for ecosystem {dependency.ecosystem}. Using fallback.")
            provider = self._providers[0] if self._providers else None

        if not provider:
            raise RuntimeError("No ecosystem providers registered in retriever.")

        try:
            return await provider.api_index(dependency.name, dependency.version)
        except Exception as e:
            logger.error(f"Failed to retrieve API index for {dependency.name}@{dependency.version}: {e}")
            return ApiIndex(package=dependency.name, version=dependency.version, signatures=())

    async def _fetch_from_source(self, source: DocSource) -> ApiIndex | None:
        # Stub for future scraping of doc sources directly (out of scope for PoC/V1)
        return None
