from __future__ import annotations

from dataclasses import dataclass

from vcase.validator.core.ir import CodeFileIR
@dataclass(frozen=True)
class ValidationError:
    """A single rule violation found during validation."""
    rule_id: str
    message: str
    context: str   # e.g. the call site or decorator that triggered this


@dataclass
class ValidationResult:
    """Aggregated outcome of validating one CodeFileIR."""
    passed: bool
    errors: list[ValidationError]


class RuleEngine:
    """
    Language-agnostic engine that validates a CodeFileIR against
    API contracts and architecture rules.

    Responsibilities:
        - validate_imports: Check if imported modules are expected in this project.
        - validate_calls: Check that call sites match the resolved API contract specs.
        - validate_architecture: Check that calls are not made in forbidden contexts.
    """

    def __init__(self,api_contracts:dict,arch_rules:list[dict]):
        self._arch_rules: list[dict] = arch_rules
        self._api_contracts: dict[str, dict[str,dict[str, dict]]] = api_contracts

    def validate_imports(self, ir: CodeFileIR, resolved_dep_names: list[str]) ->list[ValidationError]:
        """
        Question A: Is this import expected in this project?
        Cross-reference CodeFileIR.imports against the resolved dependency list.
        """
        errors:list[ValidationError] = []
        for imp in ir.imports:
            # Check if import matches a dependency exactly or is a submodule of it
            is_valid = False
            for dep in resolved_dep_names:
                if imp == dep or imp.startswith(dep + "."):
                    is_valid = True
                    break
            if not is_valid:
                errors.append(ValidationError(
                    rule_id="import-unexpected",
                    message=f"Import '{imp}' is not a recognized dependency.",
                    context=ir.filepath
                ))
        return errors
    def validate_calls(self,ir:CodeFileIR) -> list[ValidationError]:
        """
        Question B & C: Does this API exist? Are the kwargs valid?
        Cross-reference CodeFileIR.calls against the API contract specs.
        """
        import builtins
        errors:list[ValidationError] = []
        for imp in ir.calls:
            # Skip built-in functions
            if not imp.receiver and hasattr(builtins, imp.method):
                obj = getattr(builtins, imp.method)
                if callable(obj):
                    continue

            key=f"{imp.receiver}.{imp.method}" if imp.receiver else imp.method
            if key not in self._api_contracts:
                errors.append(ValidationError(
                    rule_id="api-unknown",
                    message=f"Call to '{key}' does not exist.",
                    context=ir.filepath
                ))
            else:
                spec=self._api_contracts[key]
                allowed_kwargs=spec["kwargs"]
                invalid=set(imp.kwargs)-set(allowed_kwargs)
                for bad_kwargs in invalid:
                    errors.append(ValidationError(
                        rule_id="api-invalid-kwargs",
                        message=f"Call to '{key}' has invalid kwarg '{bad_kwargs}'.",
                        context=ir.filepath
                    ))
            

        return errors

    def validate_architecture(self, ir: CodeFileIR) -> list[ValidationError]:
        """
        Question D: Is this call being made in a forbidden context?
        Cross-reference CallIR.context against architecture rules.
        """
        errors:list[ValidationError] = []
        for call in ir.calls:
            for rule in self._arch_rules:
                if (call.receiver == rule["forbidden_call"]["receiver"] or None == rule["forbidden_call"]["receiver"]) and \
                    (call.method == rule["forbidden_call"]["method"] or None == rule["forbidden_call"]["method"]) and \
                    any(ctx in call.context for ctx in rule["forbidden_contexts"]):
                    errors.append(ValidationError(
                        rule_id="arch-forbidden-call",
                        message=f"Call to '{call.receiver}.{call.method}' is made in a forbidden context '{call.context}'.",
                        context=ir.filepath
                    ))
        return errors
                
        

    def run(self, ir: CodeFileIR, resolved_dep_names: list[str]) -> ValidationResult:
        """
        Runs all three validators in sequence.
        Returns a single aggregated ValidationResult.
        """
        import_errors  = self.validate_imports(ir, resolved_dep_names)
        call_errors    = self.validate_calls(ir)
        arch_errors    = self.validate_architecture(ir)
        all_errors = import_errors + call_errors + arch_errors
        return ValidationResult(passed=len(all_errors) == 0,errors=all_errors)

        
