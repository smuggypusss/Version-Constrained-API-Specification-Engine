from __future__ import annotations

import pytest

from src.service.api_validator import ApiValidator


class TestApiValidator:

    def test_passes_when_all_calls_exist_in_index(self) -> None:
        ...

    def test_flags_call_not_present_in_api_index(self) -> None:
        ...

    def test_flags_deprecated_api_usage(self) -> None:
        ...

    def test_returns_empty_violations_for_empty_code(self) -> None:
        ...
