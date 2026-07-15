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

    def _normalize(self, name: str) -> str:
        KNOWN_IMPORT_MAPPINGS = {
            "python-dotenv": "dotenv",
            "faiss-cpu": "faiss",
            "faiss-gpu": "faiss",
            "langchain-huggingface": "langchain_huggingface",
            "scikit-learn": "sklearn",
            "pillow": "pil",
            "beautifulsoup4": "bs4",
            "pyyaml": "yaml",
            "pypdf2": "pypdf",
            "pyjwt": "jwt",
            "pydantic-settings": "pydantic_settings",
        }
        name_norm = name.lower().replace("_", "-")
        if name_norm in KNOWN_IMPORT_MAPPINGS:
            return KNOWN_IMPORT_MAPPINGS[name_norm]
        return name_norm.replace("-", "_")

    def validate_imports(self, ir: CodeFileIR, resolved_dep_names: list[str]) -> list[ValidationError]:
        """
        Question A: Is this import expected in this project?
        Cross-reference CodeFileIR.imports against the resolved dependency list.
        """
        import sys
        import importlib.metadata
        import re

        STD_LIB = getattr(sys, "stdlib_module_names", frozenset([
            "os", "sys", "json", "math", "time", "datetime", "re", "collections", "itertools", 
            "functools", "pathlib", "shutil", "tempfile", "subprocess", "logging", "hashlib", 
            "random", "urllib", "http", "socket", "select", "threading", "multiprocessing", 
            "asyncio", "unittest", "mock", "argparse", "uuid", "csv", "ast", "inspect", 
            "traceback", "weakref", "gc", "copy", "types", "contextlib", "difflib", 
            "xml", "html", "base64", "binascii", "struct", "pickle", "sqlite3", "ctypes"
        ]))

        # Expand resolved dependencies with transitive dependencies
        expanded_deps = set()
        queue = list(resolved_dep_names)
        pattern = re.compile(r"^([a-zA-Z0-9_\-]+)")
        
        while queue:
            pkg = queue.pop(0)
            pkg_norm = pkg.lower().replace("_", "-")
            if pkg_norm in expanded_deps:
                continue
            expanded_deps.add(pkg_norm)
            
            try:
                reqs = importlib.metadata.requires(pkg)
                if reqs:
                    for req in reqs:
                        match = pattern.match(req.strip())
                        if match:
                            dep_name = match.group(1)
                            dep_norm = dep_name.lower().replace("_", "-")
                            if dep_norm not in expanded_deps:
                                queue.append(dep_name)
            except Exception:
                pass

        errors: list[ValidationError] = []
        for imp in ir.imports:
            imp_top = imp.split('.')[0]
            if imp_top in STD_LIB or imp_top == "builtins":
                continue

            # Check if import matches a dependency exactly or is a submodule of it
            is_valid = False
            imp_top_norm = self._normalize(imp_top)
            imp_top_hyphen = imp_top_norm.replace("_", "-")
            
            if imp_top_hyphen in expanded_deps:
                is_valid = True
            else:
                for dep in resolved_dep_names:
                    dep_norm = self._normalize(dep)
                    if imp_top_norm == dep_norm or imp.startswith(dep + ".") or imp.startswith(dep_norm + "."):
                        is_valid = True
                        break
            if not is_valid:
                errors.append(ValidationError(
                    rule_id="import-unexpected",
                    message=f"Import '{imp}' is not a recognized dependency.",
                    context=ir.filepath
                ))
        return errors

    def validate_calls(self, ir: CodeFileIR, resolved_dep_names: list[str] | None = None) -> list[ValidationError]:
        """
        Question B & C: Does this API exist? Are the kwargs valid?
        Cross-reference CodeFileIR.calls against the API contract specs.
        """
        import builtins
        import sys
        import importlib
        
        STD_LIB = getattr(sys, "stdlib_module_names", frozenset([
            "os", "sys", "json", "math", "time", "datetime", "re", "collections", "itertools", 
            "functools", "pathlib", "shutil", "tempfile", "subprocess", "logging", "hashlib", 
            "random", "urllib", "http", "socket", "select", "threading", "multiprocessing", 
            "asyncio", "unittest", "mock", "argparse", "uuid", "csv", "ast", "inspect", 
            "traceback", "weakref", "gc", "copy", "types", "contextlib", "difflib", 
            "xml", "html", "base64", "binascii", "struct", "pickle", "sqlite3", "ctypes"
        ]))

        # Collect normalized package names of resolved dependencies
        known_packages = set()
        if resolved_dep_names:
            for dep in resolved_dep_names:
                known_packages.add(self._normalize(dep.split('.')[0]))

        errors: list[ValidationError] = []
        for imp in ir.calls:
            # Skip built-in functions
            if not imp.receiver and hasattr(builtins, imp.method):
                obj = getattr(builtins, imp.method)
                if callable(obj):
                    continue

            # Resolve aliased receivers or bare function calls
            receiver = imp.receiver
            method = imp.method
            if receiver and hasattr(ir, "aliases") and receiver in ir.aliases:
                receiver = ir.aliases[receiver]
            elif not receiver and hasattr(ir, "aliases") and method in ir.aliases:
                resolved = ir.aliases[method]
                if "." in resolved:
                    receiver, method = resolved.rsplit(".", 1)
                else:
                    receiver = None
                    method = resolved

            rec_top = receiver.split('.')[0] if receiver else None

            # Skip self, cls, and standard library modules
            if rec_top in ("self", "cls"):
                continue
            if rec_top and (rec_top in STD_LIB or rec_top == "builtins"):
                continue

            # Skip if the method is imported from a standard library module
            is_std_lib_method = False
            for imported_mod in ir.imports:
                if imported_mod in STD_LIB:
                    try:
                        mod = importlib.import_module(imported_mod)
                        if hasattr(mod, method):
                            is_std_lib_method = True
                            break
                    except Exception:
                        pass
            if is_std_lib_method:
                continue

            key = f"{receiver}.{method}" if receiver else method
            resolved_key = key
            if receiver and key not in self._api_contracts:
                rec_parts = receiver.split('.')
                rec_last = rec_parts[-1]
                target_suffix = f".{rec_last}.{method}"
                top_pkg = rec_parts[0]
                for contract_key in self._api_contracts:
                    if contract_key.startswith(top_pkg) and contract_key.endswith(target_suffix):
                        resolved_key = contract_key
                        break

            if resolved_key not in self._api_contracts:
                # If there's a receiver, check if it's a known dependency package.
                # If it's not a known dependency package, we skip checking it to avoid false positives on local variables.
                if receiver:
                    rec_top_norm = self._normalize(rec_top)
                    if rec_top_norm not in known_packages:
                        continue

                    errors.append(ValidationError(
                        rule_id="api-unknown",
                        message=f"Call to '{key}' does not exist.",
                        context=ir.filepath
                    ))
            else:
                spec = self._api_contracts[resolved_key]
                allowed_kwargs = spec["kwargs"]
                invalid = set(imp.kwargs) - set(allowed_kwargs)
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
        call_errors    = self.validate_calls(ir, resolved_dep_names)
        arch_errors    = self.validate_architecture(ir)
        all_errors = import_errors + call_errors + arch_errors
        return ValidationResult(passed=len(all_errors) == 0,errors=all_errors)

        
