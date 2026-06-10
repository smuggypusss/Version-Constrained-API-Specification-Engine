from __future__ import annotations

from pathlib import Path
import pytest

from vcase.service.resolver import DependencyResolver
from vcase.providers.python_provider import PythonProvider
from vcase.providers.base import ResolutionTier, Ecosystem


class MockPypiClient:
    async def get_latest_version(self, package: str) -> str:
        if package == "langfuse":
            return "2.5.1"
        return "1.0.0"


class TestDependencyResolver:

    @pytest.mark.asyncio
    async def test_resolves_from_lock_file_as_tier_one(
        self, fixture_repo_path: Path, sample_poetry_lock_content: str
    ) -> None:
        (fixture_repo_path / "poetry.lock").write_text(sample_poetry_lock_content, encoding="utf-8")
        client = MockPypiClient()
        provider = PythonProvider(pypi_client=client, api_index_cache=None)
        resolver = DependencyResolver(providers=[provider])
        resolved = await resolver.resolve(fixture_repo_path)
        assert len(resolved) == 3
        litellm = next(d for d in resolved if d.name == "litellm")
        assert litellm.version == "1.40.0"
        assert litellm.resolution_tier == ResolutionTier.LOCK_FILE

    @pytest.mark.asyncio
    async def test_falls_back_to_declaration_when_lock_file_missing(
        self, fixture_repo_path: Path, sample_requirements_txt_content: str
    ) -> None:
        (fixture_repo_path / "requirements.txt").write_text(sample_requirements_txt_content, encoding="utf-8")
        client = MockPypiClient()
        provider = PythonProvider(pypi_client=client, api_index_cache=None)
        resolver = DependencyResolver(providers=[provider])
        resolved = await resolver.resolve(fixture_repo_path)
        assert len(resolved) == 3
        langfuse = next(d for d in resolved if d.name == "langfuse")
        assert langfuse.version == "2.5.1"
        assert langfuse.resolution_tier == ResolutionTier.DECLARATION

    @pytest.mark.asyncio
    async def test_logs_warning_when_no_manifest_found(self, fixture_repo_path: Path) -> None:
        provider = PythonProvider(pypi_client=None, api_index_cache=None)
        resolver = DependencyResolver(providers=[provider])
        resolved = await resolver.resolve(fixture_repo_path)
        assert resolved == []

    @pytest.mark.asyncio
    async def test_normalized_output_contains_resolution_tier(
        self, fixture_repo_path: Path, sample_poetry_lock_content: str
    ) -> None:
        (fixture_repo_path / "poetry.lock").write_text(sample_poetry_lock_content, encoding="utf-8")
        client = MockPypiClient()
        provider = PythonProvider(pypi_client=client, api_index_cache=None)
        resolver = DependencyResolver(providers=[provider])
        resolved = await resolver.resolve(fixture_repo_path)
        for dep in resolved:
            assert dep.resolution_tier in (ResolutionTier.LOCK_FILE, ResolutionTier.DECLARATION)
            assert dep.ecosystem == Ecosystem.PYTHON
