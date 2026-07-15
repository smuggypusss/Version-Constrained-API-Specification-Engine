from __future__ import annotations

from pathlib import Path

import pytest

from vcase.service.detector import TechnologyDetector
from vcase.providers.python_provider import PythonProvider
from vcase.providers.node_provider import NodeProvider


class TestTechnologyDetector:

    def test_detects_python_ecosystem_from_lock_file(self, fixture_repo_path: Path) -> None:
        (fixture_repo_path / "poetry.lock").write_text("", encoding="utf-8")
        provider = PythonProvider(pypi_client=None, api_index_cache=None)
        detector = TechnologyDetector([provider])
        assert provider in detector.detect_ecosystems(fixture_repo_path)

    def test_detects_node_ecosystem_from_package_json(self, fixture_repo_path: Path) -> None:
        (fixture_repo_path / "package.json").write_text("{}", encoding="utf-8")
        provider = NodeProvider(npm_client=None)
        detector = TechnologyDetector([provider])
        assert provider in detector.detect_ecosystems(fixture_repo_path)

    def test_returns_empty_list_when_no_known_ecosystem_found(self, fixture_repo_path: Path) -> None:
        detector = TechnologyDetector([])
        assert detector.detect_ecosystems(fixture_repo_path) == []

    def test_extracts_technology_names_from_prompt(self) -> None:
        detector = TechnologyDetector([])
        prompt = "Create a FastAPI app that queries celery tasks and uses redis."
        techs = detector.detect_technologies_in_prompt(prompt)
        assert "fastapi" in techs
        assert "celery" in techs
        assert "redis" in techs

    def test_handles_prompt_with_no_known_technologies(self) -> None:
        detector = TechnologyDetector([])
        prompt = "Hello, write a hello world function."
        assert detector.detect_technologies_in_prompt(prompt) == []
