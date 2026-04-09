from src import providers

import logging
from pathlib import Path

from src.providers.base import (
    EcosystemProvider,
    RawDependency,
    ResolvedDependency,
    ResolutionTier,
)

logger = logging.getLogger(__name__)


class DependencyResolver:

    def __init__(self, providers: list[EcosystemProvider]) -> None:
        self._providers=providers

    async def resolve(self, repo_path: Path) -> list[ResolvedDependency]:
        """
        Attempt resolution in tier order.
        Tier 1: parse lock file.
        Tier 2: parse declaration file and query registry.
        Tier 3: containerized resolution (only if advanced mode is enabled).
        Logs a WARNING and returns partial results if no tier succeeds.
        """
        all_result=[]
        for provider in self._providers:
            if not provider.detect(repo_path) :
                continue
            result= await self._try_parse(provider,repo_path)
            if result is not None:
                all_result.extend(result)
                continue
            result= await self._try_containerized(provider,repo_path)
            if result is not None:
                all_result.extend(result)
            logger.warning("Could not resolve dependencies for %s",repo_path)
        return all_result
                
                
            



    async def _try_parse(self, provider: EcosystemProvider, repo_path: Path) -> list[ResolvedDependency] | None:
        try:
            dependency=provider.parse_dependencies(repo_path)
            if not dependency:
                return None
            resolved= await provider.resolve_versions(dependency)
            if not resolved:
                return None
            return resolved
        except Exception as e:
            logger.warning("Could not resolve dependencies for %s",repo_path,exc_info=True)
            return None
            


    async def _try_containerized(self, provider: EcosystemProvider, repo_path: Path) -> list[ResolvedDependency] | None:
        ...
