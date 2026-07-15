from __future__ import annotations

import logging
import tempfile
from pathlib import Path

from vcase.providers.base import InteractionConstraint, TechnologyPattern, ValidationResult, ValidationViolation
from vcase.validator.adapters.python_ast import PythonAdapter

logger = logging.getLogger(__name__)


class ArchitectureValidator:

    def _clean_code(self, code: str) -> str:
        import re
        # Try to find code block enclosed in ```python ... ``` or ``` ... ```
        pattern = r"```(?:python|py)?\n(.*?)\n```"
        matches = re.findall(pattern, code, re.DOTALL)
        if matches:
            return "\n".join(matches).strip()

        lines = code.strip().splitlines()
        if not lines:
            return code
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        return "\n".join(lines).strip()

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
        cleaned_code = self._clean_code(generated_code)
        if not cleaned_code.strip():
            return ValidationResult(passed=True, violations=[])

        # Write code to a temp file
        with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w", encoding="utf-8") as f:
            f.write(cleaned_code)
            tmp_path = Path(f.name)

        try:
            adapter = PythonAdapter()
            ir = adapter.parse(tmp_path)

            # Accumulate all constraints from parameter lists and active patterns
            all_constraints = list(constraints)
            for pattern in patterns:
                if pattern.constraint not in all_constraints:
                    all_constraints.append(pattern.constraint)

            violations = []
            for call in ir.calls:
                for constraint in all_constraints:
                    violation = None

                    if constraint.rule_name == "NO_WORKFLOW_IN_FASTAPI_ROUTE":
                        # Check if workflow.run is called in FastAPI route handler context
                        is_forbidden_call = (
                            (call.receiver == "workflow" and call.method == "run") or
                            (call.receiver == "MyWorkflow" and call.method == "run")
                        )
                        is_forbidden_ctx = any(ctx in call.context for ctx in constraint.disallowed_in)
                        if is_forbidden_call and is_forbidden_ctx:
                            violation = ValidationViolation(
                                rule_name=constraint.rule_name,
                                description=constraint.description,
                                line_number=None,
                                severity="error"
                            )

                    elif constraint.rule_name == "NO_SEQUENTIAL_LANGFUSE_LOG":
                        # Check if calling langfuse.log sequentially
                        if call.receiver == "langfuse" and call.method in ("log", "generation", "event"):
                            violation = ValidationViolation(
                                rule_name=constraint.rule_name,
                                description=constraint.description,
                                line_number=None,
                                severity="error"
                            )

                    elif constraint.rule_name == "NO_MANUAL_DB_SESSION_IN_HANDLER":
                        # Check if creating SQLAlchemy Session manually inside route handlers
                        is_session_call = (call.method == "Session" or (call.receiver == "db" and call.method == "Session"))
                        is_forbidden_ctx = any(ctx in call.context for ctx in ["app.post", "app.get", "router.post", "router.get"])
                        if is_session_call and is_forbidden_ctx:
                            violation = ValidationViolation(
                                rule_name=constraint.rule_name,
                                description=constraint.description,
                                line_number=None,
                                severity="error"
                            )

                    elif constraint.rule_name == "NO_SYNC_LLM_IN_ASYNC_ROUTE":
                        is_forbidden_call = (call.receiver == "litellm" and call.method == "completion")
                        is_forbidden_ctx = any(ctx in call.context for ctx in constraint.disallowed_in)
                        if is_forbidden_call and is_forbidden_ctx:
                            violation = ValidationViolation(
                                rule_name=constraint.rule_name,
                                description=constraint.description,
                                line_number=None,
                                severity="error"
                            )

                    if violation:
                        violations.append(violation)

            # Filter duplicates
            unique_violations = []
            seen = set()
            for v in violations:
                key = (v.rule_name, v.description)
                if key not in seen:
                    seen.add(key)
                    unique_violations.append(v)

            has_error = any(v.severity == "error" for v in unique_violations)
            return ValidationResult(
                passed=not has_error,
                violations=unique_violations
            )
        finally:
            try:
                tmp_path.unlink()
            except Exception:
                pass
