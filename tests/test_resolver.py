from __future__ import annotations

from pathlib import Path

import pytest

from src.service.resolver import DependencyResolver


class TestDependencyResolver:

    def test_resolves_from_lock_file_as_tier_one(self, fixture_repo_path: Path, sample_poetry_lock_content: str) -> None:
        ...

    def test_falls_back_to_declaration_when_lock_file_missing(self, fixture_repo_path: Path, sample_requirements_txt_content: str) -> None:
        ...

    def test_logs_warning_when_no_manifest_found(self, fixture_repo_path: Path) -> None:
        ...

    def test_normalized_output_contains_resolution_tier(self, fixture_repo_path: Path, sample_poetry_lock_content: str) -> None:
        ...
