from __future__ import annotations

import logging
from pathlib import Path

from vcase.providers.base import (
    ApiIndex,
    Ecosystem,
    EcosystemProvider,
    RawDependency,
    ResolvedDependency,
    ResolutionTier,
    DocSource,
    SourceReliability
)
from vcase.api.npm_client import NpmClient

logger = logging.getLogger(__name__)


class NodeProvider(EcosystemProvider):

    MANIFEST_FILES = ("package-lock.json", "yarn.lock", "package.json")

    def __init__(self, npm_client: NpmClient) -> None:
        self._npm_client = npm_client

    def detect(self, repo_path: Path) -> bool:
        return any((repo_path / filename).exists() for filename in self.MANIFEST_FILES)

    def parse_dependencies(self, repo_path: Path) -> list[RawDependency]:
        if (repo_path / "package-lock.json").exists():
            return self._parse_package_lock(repo_path / "package-lock.json")
        elif (repo_path / "package.json").exists():
            return self._parse_package_json(repo_path / "package.json")
        return []

    async def resolve_versions(self, deps: list[RawDependency]) -> list[ResolvedDependency]:
        resolved_dependencies = []
        if not deps:
            return resolved_dependencies
        for dep in deps:
            # Pinned version check (e.g. starts with digit)
            if dep.version_constraint and dep.version_constraint[0].isdigit():
                resolved_dependencies.append(ResolvedDependency(
                    name=dep.name,
                    version=dep.version_constraint,
                    ecosystem=Ecosystem.NODE,
                    resolution_tier=ResolutionTier.LOCK_FILE,
                ))
                continue

            try:
                latest_version = await self._npm_client.get_latest_version(dep.name)
            except Exception:
                logger.warning(f"Could not determine latest version for npm package {dep.name}")
                continue

            resolved_dependencies.append(ResolvedDependency(
                name=dep.name,
                version=latest_version,
                ecosystem=Ecosystem.NODE,
                resolution_tier=ResolutionTier.DECLARATION,
            ))
        return resolved_dependencies

    async def documentation_sources(self, package: str, version: str) -> list[DocSource]:
        sources = []
        try:
            info = await self._npm_client.get_package_info(package, version)
            
            # Check homepage
            homepage = info.get("homepage", "")
            if homepage:
                sources.append(DocSource(
                    url=homepage,
                    reliability=SourceReliability.OFFICIAL_DOCS,
                    package=package,
                    version=version
                ))
                
            # Check repository
            repo_data = info.get("repository", {})
            repo_url = ""
            if isinstance(repo_data, dict):
                repo_url = repo_data.get("url", "")
            elif isinstance(repo_data, str):
                repo_url = repo_data
                
            if repo_url:
                # Normalize git+https urls
                if repo_url.startswith("git+"):
                    repo_url = repo_url[4:]
                if repo_url.endswith(".git"):
                    repo_url = repo_url[:-4]
                sources.append(DocSource(
                    url=repo_url,
                    reliability=SourceReliability.GITHUB_RELEASE,
                    package=package,
                    version=version
                ))
        except Exception as e:
            logger.warning(f"Failed to fetch doc sources for npm package {package}@{version}: {e}")

        # Fallback registry page
        sources.append(DocSource(
            url=f"https://www.npmjs.com/package/{package}/v/{version}",
            reliability=SourceReliability.PACKAGE_REGISTRY,
            package=package,
            version=version
        ))
        sources.sort(key=lambda s: s.reliability, reverse=True)
        return sources

    async def api_index(self, package: str, version: str) -> ApiIndex:
        # Static validation for Node.js APIs is a stub as Javascript AST parsing is out of scope.
        # Returns an empty ApiIndex.
        return ApiIndex(package=package, version=version, signatures=())

    def _parse_package_lock(self, lock_path: Path) -> list[RawDependency]:
        import json
        raw_dependencies = []
        try:
            with open(lock_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            # v2/v3 lockfile parsing
            packages = data.get("packages", {})
            if packages:
                for path, pkg in packages.items():
                    if not path:
                        continue
                    name = path.replace("node_modules/", "", 1)
                    if "node_modules/" in name:
                        name = name.split("node_modules/")[-1]
                    version = pkg.get("version", "")
                    if name and version:
                        raw_dependencies.append(RawDependency(name, version, Ecosystem.NODE))
            
            # v1 lockfile parsing fallback
            dependencies = data.get("dependencies", {})
            if not raw_dependencies and dependencies:
                for name, dep in dependencies.items():
                    version = dep.get("version", "")
                    if name and version:
                        raw_dependencies.append(RawDependency(name, version, Ecosystem.NODE))
        except Exception as e:
            logger.warning(f"Failed to parse package-lock.json: {e}")
        return raw_dependencies

    def _parse_package_json(self, pkg_path: Path) -> list[RawDependency]:
        import json
        raw_dependencies = []
        try:
            with open(pkg_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            deps = data.get("dependencies", {})
            dev_deps = data.get("devDependencies", {})
            
            combined = {**deps, **dev_deps}
            for name, version in combined.items():
                if isinstance(version, str):
                    raw_dependencies.append(RawDependency(name, version, Ecosystem.NODE))
        except Exception as e:
            logger.warning(f"Failed to parse package.json: {e}")
        return raw_dependencies
