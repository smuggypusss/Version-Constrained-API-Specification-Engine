from __future__ import annotations

import ast
import logging
from pathlib import Path

from vcase.providers.base import ApiIndex, ApiSignature, ApiParameter

logger = logging.getLogger(__name__)


class AstParser:
    """
    A service that reads Python source code files and extracts
    function signatures into structured ApiIndex objects using the built-in ast module.
    """

    def parse_file(
        self,
        package_name: str,
        package_version: str,
        filepath: Path,
        module_prefix: str | None = None
    ) -> ApiIndex:
        """
        Reads the given Python file, walks the Abstract Syntax Tree, 
        and extracts all function signatures.
        """
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
            tree = ast.parse(content, filename=str(filepath))
        except Exception as e:
            logger.error(f"Failed to parse AST for {filepath}: {e}")
            return ApiIndex(package=package_name, version=package_version, signatures=())

        if module_prefix is None:
            # Determine the module prefix relative to the package name
            parts = filepath.parts
            try:
                pkg_idx = next(i for i, part in enumerate(parts) if part.lower() == package_name.lower())
                rel_parts = parts[pkg_idx:]
            except StopIteration:
                rel_parts = (package_name, filepath.name)

            rel_parts_list = list(rel_parts)
            if rel_parts_list:
                rel_parts_list[-1] = Path(rel_parts_list[-1]).stem
            if rel_parts_list and rel_parts_list[-1] == "__init__":
                rel_parts_list.pop()

            module_prefix = ".".join(rel_parts_list) if rel_parts_list else package_name

        visitor = _SignatureVisitor(module_prefix, self)
        visitor.visit(tree)

        return ApiIndex(
            package=package_name,
            version=package_version,
            signatures=tuple(visitor.signatures)
        )

    def _extract_return_type(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
        """
        Helper method: Parses the 'node.returns' AST node and extracts the type hint as a string.
        (e.g., extracting 'str' from '-> str:')
        """
        if not node.returns:
            return "Any"
        return self._get_type_hint(node.returns)

    def _extract_parameters(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> tuple[ApiParameter, ...]:
        """
        Helper method: Parses the 'node.args.args' AST list and builds an ApiParameter 
        object for every argument.
        """
        parameters: list[ApiParameter] = []

        # Positional defaults map to the last N arguments
        defaults = node.args.defaults
        num_defaults = len(defaults)
        args = node.args.args
        num_args = len(args)

        for i, arg in enumerate(args):
            if arg.arg in ("self", "cls"):
                continue

            name = arg.arg
            type_hint = self._get_type_hint(arg.annotation)
            has_default = (i >= num_args - num_defaults)
            required = not has_default

            parameters.append(ApiParameter(
                name=name,
                type_hint=type_hint,
                required=required,
                description=""
            ))

        # *args
        if getattr(node.args, "vararg", None) is not None:
            vararg_name = node.args.vararg.arg
            parameters.append(ApiParameter(
                name=f"*{vararg_name}",
                type_hint="Any",
                required=False,
                description=""
            ))

        # Keyword-only arguments
        kwonlyargs = node.args.kwonlyargs
        kw_defaults = node.args.kw_defaults
        for i, arg in enumerate(kwonlyargs):
            name = arg.arg
            type_hint = self._get_type_hint(arg.annotation)
            has_default = (i < len(kw_defaults) and kw_defaults[i] is not None)
            required = not has_default

            parameters.append(ApiParameter(
                name=name,
                type_hint=type_hint,
                required=required,
                description=""
            ))

        # **kwargs
        if getattr(node.args, "kwarg", None) is not None:
            kwarg_name = node.args.kwarg.arg
            parameters.append(ApiParameter(
                name=f"**{kwarg_name}",
                type_hint="Any",
                required=False,
                description=""
            ))

        return tuple(parameters)

    def _get_type_hint(self, node: ast.expr | None) -> str:
        """Converts an AST annotation node into a string representation."""
        if node is None:
            return "Any"
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Constant):
            return str(node.value)
        if isinstance(node, ast.Attribute):
            val = self._get_type_hint(node.value)
            return f"{val}.{node.attr}"
        if isinstance(node, ast.Subscript):
            val = self._get_type_hint(node.value)
            slc = self._get_type_hint(node.slice)
            return f"{val}[{slc}]"
        if isinstance(node, ast.Tuple):
            return f"tuple[{', '.join(self._get_type_hint(el) for el in node.elts)}]"
        if isinstance(node, ast.List):
            return f"list[{', '.join(self._get_type_hint(el) for el in node.elts)}]"
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
            left = self._get_type_hint(node.left)
            right = self._get_type_hint(node.right)
            return f"{left} | {right}"
        
        # Handle ast.Index for legacy Python versions (3.8 compatibility)
        if hasattr(ast, "Index") and isinstance(node, ast.Index):
            return self._get_type_hint(node.value)

        return "Any"


class _SignatureVisitor(ast.NodeVisitor):
    """Internal visitor to walk modules/classes and collect signatures."""

    def __init__(self, module_prefix: str, parser: AstParser) -> None:
        self.signatures: list[ApiSignature] = []
        self._scope_stack: list[str] = [module_prefix]
        self._parser = parser

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        if node.name.startswith("_"):
            self.generic_visit(node)
            return
        self._scope_stack.append(node.name)
        self.generic_visit(node)
        self._scope_stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._process_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._process_function(node)

    def _process_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        if node.name.startswith("_"):
            return

        parent_scope = ".".join(self._scope_stack)
        qualified_name = f"{parent_scope}.{node.name}"

        return_type = self._parser._extract_return_type(node)
        parameters = self._parser._extract_parameters(node)

        deprecated = False
        deprecation_note = ""
        for decorator in node.decorator_list:
            dec_name = self._get_decorator_name(decorator)
            if dec_name and "deprecat" in dec_name.lower():
                deprecated = True
                deprecation_note = f"Deprecated via decorator @{dec_name}"
                break

        docstring = ast.get_docstring(node)
        if docstring and "deprecated" in docstring.lower():
            deprecated = True
            deprecation_note = deprecation_note or "Deprecated in docstring"

        self.signatures.append(ApiSignature(
            qualified_name=qualified_name,
            parameters=parameters,
            return_type=return_type,
            available_since="",
            deprecated=deprecated,
            deprecation_note=deprecation_note
        ))

    def _get_decorator_name(self, node: ast.expr) -> str | None:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            val = self._get_decorator_name(node.value)
            if val:
                return f"{val}.{node.attr}"
        if isinstance(node, ast.Call):
            return self._get_decorator_name(node.func)
        return None
