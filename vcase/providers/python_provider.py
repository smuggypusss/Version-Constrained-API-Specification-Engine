from __future__ import annotations
import logging
from pathlib import Path
import tomllib
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
from vcase.api.pypi_client import PypiClient
from vcase.service.api_index_cache import ApiIndexCache

logger = logging.getLogger(__name__)

class PythonProvider(EcosystemProvider):

    MANIFEST_FILES = ("poetry.lock", "requirements.txt", "pyproject.toml")
    def __init__(self, pypi_client: PypiClient, api_index_cache: ApiIndexCache | None = None) -> None:
        self.pypi_client = pypi_client
        if api_index_cache is None and pypi_client is not None and hasattr(pypi_client, "_client"):
            api_index_cache = ApiIndexCache(pypi_client._client)
        self._api_index_cache = api_index_cache
    def detect(self, repo_path: Path) -> bool:
        return any((repo_path / filename).exists() for filename in self.MANIFEST_FILES)



    def parse_dependencies(self, repo_path: Path) -> list[RawDependency]:
        if (repo_path / "poetry.lock").exists() :
            return self._parse_poetry_lock(repo_path / "poetry.lock")
        elif (repo_path / "requirements.txt").exists():
            return self._parse_requirements_txt(repo_path / "requirements.txt")
        elif (repo_path / "pyproject.toml").exists():
            return self._parse_pyproject_toml(repo_path / "pyproject.toml")
        else:
            logger.warning("No manifest files found in %s",repo_path)
            return []
            

    async def resolve_versions(self, deps: list[RawDependency]) -> list[ResolvedDependency]:
        resolved_dependencies=[]
        if not deps:
            return resolved_dependencies
        for dep in deps:
            if dep.version_constraint and  dep.version_constraint[0].isdigit():
                resolved_dependencies.append(ResolvedDependency(
                    name=dep.name,
                    version=dep.version_constraint,
                    ecosystem=Ecosystem.PYTHON,
                    resolution_tier=ResolutionTier.LOCK_FILE,
                ))
                continue
            try:
                latest_version=await self.pypi_client.get_latest_version(dep.name)
            except Exception:
                logger.warning("Could not determine latest version for %s",dep.name)
                continue
            resolved_dependency=ResolvedDependency(
                name=dep.name,
                version=latest_version,
                ecosystem=Ecosystem.PYTHON,
                resolution_tier=ResolutionTier.DECLARATION,
            )
            resolved_dependencies.append(resolved_dependency)
       
        return resolved_dependencies

    async def documentation_sources(self, package: str, version: str) -> list[DocSource]:
        sources = []
        try:
            info = await self.pypi_client.get_package_info(package, version)
            urls = info.get("info", {}).get("project_urls", {}) or {}
            for label, url in urls.items():
                label_lower = label.lower()
                if "documentation" in label_lower or "docs" in label_lower:
                    sources.append(DocSource(
                        url=url,
                        reliability=SourceReliability.OFFICIAL_DOCS,
                        package=package,
                        version=version
                    ))
                elif "home" in label_lower or "homepage" in label_lower:
                    sources.append(DocSource(
                        url=url,
                        reliability=SourceReliability.OFFICIAL_DOCS,
                        package=package,
                        version=version
                    ))
                elif "code" in label_lower or "source" in label_lower or "github" in label_lower:
                    sources.append(DocSource(
                        url=url,
                        reliability=SourceReliability.GITHUB_RELEASE,
                        package=package,
                        version=version
                    ))
            sources.append(DocSource(
                url=f"https://pypi.org/project/{package}/{version}/",
                reliability=SourceReliability.PACKAGE_REGISTRY,
                package=package,
                version=version
            ))
        except Exception as e:
            logger.warning(f"Failed to fetch doc sources for {package}@{version}: {e}")
            sources.append(DocSource(
                url=f"https://pypi.org/project/{package}/{version}/",
                reliability=SourceReliability.PACKAGE_REGISTRY,
                package=package,
                version=version
            ))
        sources.sort(key=lambda s: s.reliability, reverse=True)
        return sources

    async def api_index(self, package: str, version: str) -> ApiIndex:
        index = await self._api_index_cache.get(package, version)
        if index:
            return index
        return ApiIndex(package=package, version=version, signatures=())

    def _parse_poetry_lock(self, lock_path: Path) -> list[RawDependency]:
        with open(lock_path,"rb") as f:
            data_poetry=tomllib.load(f)
        package_list=data_poetry.get("package",[])
        raw_dependencies=[]
        for package in package_list:
            name=package.get("name","")
            version=package.get("version","")
            if  not name or not version:
                logger.warning("Skipping dependency with missing name or version: %s",package)
                continue
            ecosystem=Ecosystem.PYTHON
            raw_dependency=RawDependency(name,version,ecosystem)
            raw_dependencies.append(raw_dependency)
        return raw_dependencies

    def _parse_requirements_txt(self, req_path: Path) -> list[RawDependency]:
        with open(req_path,"r") as f:
            data_req=f.read()
        raw_dependencies=[]
        for line in data_req.splitlines():
            line=line.strip()
            if not line or line.startswith("#"):
                continue
            if "==" in line:
                name,version=line.split("==",1)
                name, version = name.strip(), version.strip()
            elif "~=" in line:
                name,version=line.split("~=",1)
                name, version = name.strip(), "~=" + version.strip()
            elif ">=" in line:
                name,version=line.split(">=",1)
                name, version = name.strip(), ">=" + version.strip()
            elif "<=" in line:
                name,version=line.split("<=",1)
                name, version = name.strip(), "<=" + version.strip()
            elif ">" in line:
                name,version=line.split(">",1)
                name, version = name.strip(), ">" + version.strip()
            elif "<" in line:
                name,version=line.split("<",1)
                name, version = name.strip(), "<" + version.strip()
            else:
                name=line.strip()
                version=""
                logger.warning("No specific version present for the package %s",name)
            ecosystem=Ecosystem.PYTHON
            raw_dependency=RawDependency(name,version,ecosystem)
            raw_dependencies.append(raw_dependency)
        return raw_dependencies

    def _parse_pyproject_toml(self, toml_path: Path) -> list[RawDependency]:
        with open(toml_path,"rb") as f:
            data_pyproject=tomllib.load(f)
        raw_dependencies=[]
        if project_data:=data_pyproject.get("project",{}):
            dependencies_list=project_data.get("dependencies",[])
            for dependency in dependencies_list:
                if "==" in dependency:
                    name,version=dependency.split("==",1)
                    name, version = name.strip(), version.strip()
                elif "~=" in dependency:
                    name,version=dependency.split("~=",1)
                    name, version = name.strip(), "~=" + version.strip()
                elif ">=" in dependency:
                    name,version=dependency.split(">=",1)
                    name, version = name.strip(), ">=" + version.strip()
                elif "<=" in dependency:
                    name,version=dependency.split("<=",1)
                    name, version = name.strip(), "<=" + version.strip()
                elif ">" in dependency:
                    name,version=dependency.split(">",1)
                    name, version = name.strip(), ">" + version.strip()
                elif "<" in dependency:
                    name,version=dependency.split("<",1)
                    name, version = name.strip(), "<" + version.strip()
                else:
                    name=dependency.strip()
                    version=""
                    logger.warning("No specific version present for the package %s",name)
                ecosystem=Ecosystem.PYTHON
                raw_dependency=RawDependency(name,version,ecosystem)
                raw_dependencies.append(raw_dependency)


        if dependencies_data:=data_pyproject.get("tool",{}).get("poetry",{}).get("dependencies",{}):
            for name,version in dependencies_data.items():
                if not isinstance(version,str):
                    version=""
                ecosystem=Ecosystem.PYTHON
                raw_dependency=RawDependency(name,version,ecosystem)
                raw_dependencies.append(raw_dependency)
            
        return raw_dependencies
            
