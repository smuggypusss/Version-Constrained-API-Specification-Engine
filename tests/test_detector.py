from __future__ import annotations

from pathlib import Path

import pytest

from src.service.detector import TechnologyDetector


class TestTechnologyDetector:

    def test_detects_python_ecosystem_from_lock_file(self, fixture_repo_path: Path) -> None:
        ...

    def test_detects_node_ecosystem_from_package_json(self, fixture_repo_path: Path) -> None:
        ...

    def test_returns_empty_list_when_no_known_ecosystem_found(self, fixture_repo_path: Path) -> None:
        ...

    def test_extracts_technology_names_from_prompt(self) -> None:
        ...

    def test_handles_prompt_with_no_known_technologies(self) -> None:
        ...
