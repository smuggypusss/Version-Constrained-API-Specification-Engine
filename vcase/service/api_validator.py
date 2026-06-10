from __future__ import annotations

import logging
import tempfile
from pathlib import Path

from vcase.providers.base import ApiIndex, ValidationResult, ValidationViolation
from vcase.validator.adapters.python_ast import PythonAdapter
from vcase.validator.core.rules_engine import RuleEngine

logger = logging.getLogger(__name__)


class ApiValidator:

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
        api_indexes: list[ApiIndex],
        extra_whitelisted_imports: list[str] | None = None
    ) -> ValidationResult:
        cleaned_code = self._clean_code(generated_code)
        if not cleaned_code.strip():
            return ValidationResult(passed=True, violations=[])

        with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w", encoding="utf-8") as f:
            f.write(cleaned_code)
            tmp_path = Path(f.name)

        try:
            adapter = PythonAdapter()
            ir = adapter.parse(tmp_path)
            
            # Map api_indexes to RuleEngine's format
            api_contracts = {}
            for index in api_indexes:
                package = index.package
                for sig in index.signatures:
                    sig_kwargs = [p.name for p in sig.parameters]
                    has_kwargs = any(p.name.startswith("**") for p in sig.parameters)

                    contract = {
                        "kwargs": sig_kwargs,
                        "deprecated": sig.deprecated,
                        "deprecation_note": sig.deprecation_note
                    }

                    keys = []
                    # 1. Full qualified name (e.g. litellm.main.completion)
                    keys.append(sig.qualified_name)
                    
                    # 2. Simple name (e.g. completion)
                    parts = sig.qualified_name.split(".")
                    simple_name = parts[-1]
                    keys.append(simple_name)
                    
                    # 3. Package name + simple name (e.g. litellm.completion)
                    keys.append(f"{package}.{simple_name}")
                    
                    # 4. Handle class names if present
                    if len(parts) >= 3:
                        class_name = parts[-2]
                        if class_name and class_name[0].isupper():
                            keys.append(f"{package}.{class_name}.{simple_name}")
                            keys.append(f"{class_name}.{simple_name}")

                    # If this signature has **kwargs, dynamically extend its allowed kwargs with
                    # the keyword arguments passed at matching call sites.
                    if has_kwargs:
                        for call in ir.calls:
                            call_key = f"{call.receiver}.{call.method}" if call.receiver else call.method
                            if call_key in keys or call.method in keys:
                                for kw in call.kwargs:
                                    if kw not in contract["kwargs"]:
                                        contract["kwargs"].append(kw)

                    for key in keys:
                        api_contracts[key] = contract

            # Instantiate and run RuleEngine
            resolved_dep_names = [index.package for index in api_indexes]
            # Include submodules and alternate namings for standard imports (e.g. temporalio vs workflow client)
            # Add package names
            for name in list(resolved_dep_names):
                resolved_dep_names.append(name.lower())
                if name.lower() == "temporalio":
                    resolved_dep_names.append("temporalio.client")
                    resolved_dep_names.append("temporalio.workflow")
            
            if extra_whitelisted_imports:
                for name in extra_whitelisted_imports:
                    resolved_dep_names.append(name)
                    resolved_dep_names.append(name.lower())
                    
            engine = RuleEngine(api_contracts=api_contracts, arch_rules=[])
            result = engine.run(ir, resolved_dep_names)

            # Map RuleEngine's ValidationResult errors to ValidationViolation objects
            violations = []
            for err in result.errors:
                violations.append(ValidationViolation(
                    rule_name=err.rule_id,
                    description=err.message,
                    line_number=None,
                    severity="error"
                ))

            # Additional check for deprecated APIs
            for imp in ir.calls:
                key = f"{imp.receiver}.{imp.method}" if imp.receiver else imp.method
                for k in (key, imp.method):
                    if k in api_contracts and api_contracts[k].get("deprecated"):
                        violations.append(ValidationViolation(
                            rule_name="api-deprecated",
                            description=f"Call to '{key}' is deprecated: {api_contracts[k].get('deprecation_note')}",
                            line_number=None,
                            severity="warning"
                        ))

            # Filter out warning duplicates
            seen_violations = set()
            unique_violations = []
            for v in violations:
                v_key = (v.rule_name, v.description)
                if v_key not in seen_violations:
                    seen_violations.add(v_key)
                    unique_violations.append(v)

            # Return final result
            passed = all(v.severity == "error" for v in unique_violations) == False or len(unique_violations) == 0
            # Wait, if there are only warnings, does it pass? Yes. If any error, passed is False.
            has_error = any(v.severity == "error" for v in unique_violations)
            return ValidationResult(
                passed=not has_error,
                violations=unique_violations
            )
        finally:
            # Clean up the temporary file
            try:
                tmp_path.unlink()
            except Exception:
                pass
