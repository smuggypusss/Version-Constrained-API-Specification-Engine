from __future__ import annotations

import pytest

from vcase.service.architecture_validator import ArchitectureValidator
from vcase.providers.base import InteractionConstraint, TechnologyPattern


class TestArchitectureValidator:

    def test_flags_temporal_workflow_called_inside_fastapi_handler(self) -> None:
        validator = ArchitectureValidator()
        code = """
import fastapi
import workflow

app = fastapi.FastAPI()

@app.post("/workflow")
async def run():
    await workflow.run()
"""
        constraint = InteractionConstraint(
            rule_name="NO_WORKFLOW_IN_FASTAPI_ROUTE",
            allowed_in=(),
            disallowed_in=("app.post", "app.get"),
            description="Temporal workflows cannot run directly in FastAPI route handlers."
        )
        result = validator.validate(code, [], [constraint])
        assert result.passed is False
        assert any(v.rule_name == "NO_WORKFLOW_IN_FASTAPI_ROUTE" for v in result.violations)

    def test_flags_langfuse_used_as_sequential_log_instead_of_callback(self) -> None:
        validator = ArchitectureValidator()
        code = """
import langfuse
import litellm

# Sequential log call
langfuse.log()
"""
        constraint = InteractionConstraint(
            rule_name="NO_SEQUENTIAL_LANGFUSE_LOG",
            allowed_in=(),
            disallowed_in=("sequential_flow",),
            description="Langfuse integration with LiteLLM should use callbacks."
        )
        result = validator.validate(code, [], [constraint])
        assert result.passed is False
        assert any(v.rule_name == "NO_SEQUENTIAL_LANGFUSE_LOG" for v in result.violations)

    def test_flags_sqlalchemy_session_instantiated_inside_handler(self) -> None:
        validator = ArchitectureValidator()
        code = """
import fastapi
app = fastapi.FastAPI()

@app.post("/items")
def create_item():
    db = Session()
"""
        constraint = InteractionConstraint(
            rule_name="NO_MANUAL_DB_SESSION_IN_HANDLER",
            allowed_in=(),
            disallowed_in=("handler_body",),
            description="Do not manually create DB session inside handlers."
        )
        result = validator.validate(code, [], [constraint])
        assert result.passed is False
        assert any(v.rule_name == "NO_MANUAL_DB_SESSION_IN_HANDLER" for v in result.violations)

    def test_passes_valid_temporal_client_usage_outside_handler(self) -> None:
        validator = ArchitectureValidator()
        code = """
import temporalio
import workflow

async def run_worker():
    await workflow.run()
"""
        constraint = InteractionConstraint(
            rule_name="NO_WORKFLOW_IN_FASTAPI_ROUTE",
            allowed_in=(),
            disallowed_in=("app.post", "app.get"),
            description="Temporal workflows cannot run directly in FastAPI route handlers."
        )
        result = validator.validate(code, [], [constraint])
        assert result.passed is True
        assert len(result.violations) == 0

    def test_passes_when_no_constraints_apply_to_detected_stack(self) -> None:
        validator = ArchitectureValidator()
        code = "print('hello')"
        result = validator.validate(code, [], [])
        assert result.passed is True
        assert len(result.violations) == 0
