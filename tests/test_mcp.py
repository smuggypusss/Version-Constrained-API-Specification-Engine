from __future__ import annotations

import pytest
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

from vcase.mcp import vcase_get_context, vcase_validate_code, vcase_run_generation
from vcase.providers.base import ResolvedDependency, Ecosystem, ResolutionTier, ApiIndex, ApiSignature
from vcase.service.resolver import DependencyResolver
from vcase.service.retriever import DocumentationRetriever


@pytest.mark.asyncio
async def test_vcase_get_context_invalid_path() -> None:
    res = await vcase_get_context("test prompt", "/nonexistent/path")
    assert "Error: Repository path" in res


@pytest.mark.asyncio
async def test_vcase_get_context_valid_path() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir)
        (repo_path / "requirements.txt").write_text("fastapi>=0.110.0", encoding="utf-8")

        with patch.object(DependencyResolver, "resolve", new_callable=AsyncMock) as mock_resolve, \
             patch.object(DocumentationRetriever, "retrieve", new_callable=AsyncMock) as mock_retrieve:
             
            mock_resolve.return_value = [
                ResolvedDependency("fastapi", "0.110.0", Ecosystem.PYTHON, ResolutionTier.LOCK_FILE)
            ]
            mock_retrieve.return_value = ApiIndex(
                package="fastapi",
                version="0.110.0",
                signatures=(
                    ApiSignature(
                        qualified_name="fastapi.FastAPI",
                        parameters=(),
                        return_type="FastAPI",
                        available_since="",
                        deprecated=False
                    ),
                )
            )

            res = await vcase_get_context("Write a fastapi endpoint", str(repo_path))
            assert "fastapi" in res
            assert "## fastapi" in res


@pytest.mark.asyncio
async def test_vcase_validate_code_passes() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir)
        (repo_path / "requirements.txt").write_text("fastapi>=0.110.0", encoding="utf-8")

        with patch.object(DependencyResolver, "resolve", new_callable=AsyncMock) as mock_resolve, \
             patch.object(DocumentationRetriever, "retrieve", new_callable=AsyncMock) as mock_retrieve:
             
            mock_resolve.return_value = [
                ResolvedDependency("fastapi", "0.110.0", Ecosystem.PYTHON, ResolutionTier.LOCK_FILE)
            ]
            mock_retrieve.return_value = ApiIndex(
                package="fastapi",
                version="0.110.0",
                signatures=(
                    ApiSignature(
                        qualified_name="fastapi.FastAPI",
                        parameters=(),
                        return_type="FastAPI",
                        available_since="",
                        deprecated=False
                    ),
                )
            )

            code = "import fastapi\napp = fastapi.FastAPI()"
            res = await vcase_validate_code(code, str(repo_path))
            assert "Validation passed successfully" in res


@pytest.mark.asyncio
async def test_vcase_validate_code_fails() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir)
        (repo_path / "requirements.txt").write_text("fastapi>=0.110.0", encoding="utf-8")

        with patch.object(DependencyResolver, "resolve", new_callable=AsyncMock) as mock_resolve, \
             patch.object(DocumentationRetriever, "retrieve", new_callable=AsyncMock) as mock_retrieve:
             
            mock_resolve.return_value = [
                ResolvedDependency("fastapi", "0.110.0", Ecosystem.PYTHON, ResolutionTier.LOCK_FILE)
            ]
            mock_retrieve.return_value = ApiIndex(
                package="fastapi",
                version="0.110.0",
                signatures=()
            )

            # Invalid import
            code = "import invalid_pkg"
            res = await vcase_validate_code(code, str(repo_path))
            assert "Validation failed" in res
            assert "import-unexpected" in res


@pytest.mark.asyncio
async def test_vcase_run_generation_mocked() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir)
        (repo_path / "requirements.txt").write_text("fastapi>=0.110.0", encoding="utf-8")

        # Mock the orchestrator's run method
        with patch("vcase.mcp.create_orchestrator") as mock_create:
            mock_orchestrator = AsyncMock()
            mock_orchestrator.run.return_value = "generated_code_here"
            mock_create.return_value = mock_orchestrator

            res = await vcase_run_generation(
                prompt="test prompt",
                repo_path=str(repo_path),
                model="test-model",
                provider="openai",
                api_key="test-key"
            )
            assert res == "generated_code_here"
            mock_create.assert_called_once()
            mock_orchestrator.run.assert_called_once_with("test prompt", repo_path, target_file=None)
