from __future__ import annotations

import logging

from src.providers.base import ApiIndex, ValidationResult

logger = logging.getLogger(__name__)


class LlmValidator:

    def __init__(self, model_name: str) -> None:
        ...

    async def validate(
        self,
        generated_code: str,
        api_indexes: list[ApiIndex],
        violation_context: str,
    ) -> ValidationResult:
        """
        Layer 3: LLM escalation.
        Triggered only when Layer 1 or Layer 2 finds an ambiguous violation.
        Uses a small model with a constrained few-shot prompt.
        """
        ...

    def _build_validation_prompt(self, code: str, indexes: list[ApiIndex], context: str) -> str:
        ...
