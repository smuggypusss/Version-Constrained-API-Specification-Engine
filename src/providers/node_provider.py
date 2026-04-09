from __future__ import annotations

import logging
from pathlib import Path

from src.providers.base import ApiIndex, Ecosystem, EcosystemProvider, RawDependency, ResolvedDependency

logger = logging.getLogger(__name__)


class NodeProvider(EcosystemProvider):

    MANIFEST_FILES = ("package-lock.json", "yarn.lock", "package.json")

    def detect(self, repo_path: Path) -> bool:
        ...

    def parse_dependencies(self, repo_path: Path) -> list[RawDependency]:
        ...

    def resolve_versions(self, deps: list[RawDependency]) -> list[ResolvedDependency]:
        ...

    def documentation_sources(self, package: str, version: str) -> list:
        ...

    def api_index(self, package: str, version: str) -> ApiIndex:
        ...

    def _parse_package_lock(self, lock_path: Path) -> list[RawDependency]:
        ...

    def _parse_package_json(self, pkg_path: Path) -> list[RawDependency]:
        ...
