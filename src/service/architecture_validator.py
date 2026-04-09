from __future__ import annotations

import logging

from src.providers.base import InteractionConstraint, TechnologyPattern, ValidationResult

logger = logging.getLogger(__name__)


class ArchitectureValidator:

    def validate(
        self,
        generated_code: str,
        patterns: list[TechnologyPattern],
        constraints: list[InteractionConstraint],
    ) -> ValidationResult:
        """
        Layer 2: Architecture pattern check.
        Verify that the generated code composes technologies according to known valid patterns.
        Flag any composition that violates interaction constraints.
        """
        ...

    def _detect_context(self, code: str) -> list[str]:
        """Identify architectural contexts present in the code (e.g. fastapi_handler, temporal_client)."""
        ...

    def _check_constraint(self, context: list[str], constraint: InteractionConstraint) -> bool:
        ...
