from __future__ import annotations

import pytest
from pathlib import Path


@pytest.fixture
def fixture_repo_path(tmp_path: Path) -> Path:
    """Returns a temporary directory simulating a Python repository."""
    return tmp_path


@pytest.fixture
def sample_poetry_lock_content() -> str:
    return """\
[[package]]
name = "litellm"
version = "1.40.0"

[[package]]
name = "langfuse"
version = "2.5.1"

[[package]]
name = "temporalio"
version = "1.6.0"
"""


@pytest.fixture
def sample_requirements_txt_content() -> str:
    return """\
litellm==1.40.0
langfuse>=2.0.0
temporalio==1.6.0
"""
