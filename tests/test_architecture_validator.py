from __future__ import annotations

import pytest

from src.service.architecture_validator import ArchitectureValidator


class TestArchitectureValidator:

    def test_flags_temporal_workflow_called_inside_fastapi_handler(self) -> None:
        ...

    def test_flags_langfuse_used_as_sequential_log_instead_of_callback(self) -> None:
        ...

    def test_flags_sqlalchemy_session_instantiated_inside_handler(self) -> None:
        ...

    def test_passes_valid_temporal_client_usage_outside_handler(self) -> None:
        ...

    def test_passes_when_no_constraints_apply_to_detected_stack(self) -> None:
        ...
