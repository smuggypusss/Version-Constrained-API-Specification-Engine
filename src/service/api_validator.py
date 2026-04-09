from __future__ import annotations

import logging

from src.providers.base import ApiIndex, ValidationResult

logger = logging.getLogger(__name__)


class ApiValidator:

    def validate(self, generated_code: str, api_indexes: list[ApiIndex]) -> ValidationResult:
        """
        Layer 1: Static AST check.
        Extract all function calls from generated_code.
        Cross-reference each against the provided api_indexes.
        Flag any call that does not exist in the index.
        """
        ...

    def _extract_function_calls(self, code: str) -> list[str]:
        ...

    def _is_in_index(self, call: str, indexes: list[ApiIndex]) -> bool:
        ...
