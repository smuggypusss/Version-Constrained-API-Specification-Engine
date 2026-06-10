from __future__ import annotations

import ast
import logging
from pathlib import Path

from vcase.validator.core.ir import CallIR, CodeFileIR

logger = logging.getLogger(__name__)

class PythonAdapter:
    """
    Converts a raw Python source file into a normalized CodeFileIR
    using Python's built-in `ast` module.

    This is the ONLY class that knows about Python AST internals.
    All other classes operate purely on CodeFileIR.

    Pipeline:
        .py file → ast.parse() → walk tree → CodeFileIR
    """

    def parse(self, filepath: Path) -> CodeFileIR:
        """
        Entry point. Reads the file, parses the AST, delegates to
        private helpers, and returns a fully-populated CodeFileIR.
        """
        with open(filepath, "r", encoding="utf-8") as f:
            try:
                tree = ast.parse(f.read(), filename=str(filepath))
            except SyntaxError as e:
                logger.error(f"Syntax error in {filepath}: {e}")
                return CodeFileIR(
                    filepath=str(filepath),
                    imports=[],
                    calls=[],
                )
        
        return CodeFileIR(
            filepath=str(filepath),
            imports=self._extract_imports(tree),
            calls=self._extract_calls(tree),
        )

    def _extract_imports(self, tree: ast.Module) -> list[str]:
        """
        Walks the AST looking for ast.Import and ast.ImportFrom nodes.
        Returns a flat list of top-level module names.

        Example:
            'from litellm import completion' -> ["litellm"]
            'import httpx'                  -> ["httpx"]
        """
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append(node.module)
        return list(set(imports))

    def _extract_calls(self, tree: ast.Module) -> list[CallIR]:
        """
        Walks the AST using a CallExtractor NodeVisitor.
        Returns a list of CallIR objects for every call site found.

        Handles two AST shapes:
            ast.Name      -> bare function call:  completion(...)
            ast.Attribute -> method call:          litellm.completion(...)
        """
        extractor = _CallExtractor()
        extractor.visit(tree)
        return extractor.calls


class _CallExtractor(ast.NodeVisitor):
    """
    Internal AST NodeVisitor that traverses the tree and
    collects all function/method call sites and their enclosing context.

    Context tracking:
        Maintains a context_stack to detect calls inside decorated functions
        e.g. @app.post route handlers, to enable architecture rule checking.
    """

    def __init__(self) -> None:
        self.calls: list[CallIR] = []
        self._context_stack: list[list[str]] = []

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """
        Pushes decorator context onto the stack before visiting children.
        Pops it after, maintaining correct scope.
        """
        self._context_stack.append(
            [name for d in node.decorator_list if (name := self._get_decorater_name(d)) is not None]
        )
        self.generic_visit(node)
        self._context_stack.pop()


    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Same as above but for synchronous function definitions."""
        self._context_stack.append(
            [name for d in node.decorator_list if (name := self._get_decorater_name(d)) is not None]
        )
        self.generic_visit(node)
        self._context_stack.pop()

    def _get_decorater_name(self, node: ast.expr) -> str | None:
        """
        Safely resolves the receiver of an attribute call.
        e.g. for `litellm.completion`, extracts "litellm".
        Returns None if the receiver is too complex to resolve statically.
        """
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            receiver = self._get_decorater_name(node.value)
            if receiver:
                return f"{receiver}.{node.attr}"
        elif isinstance(node, ast.Call):
            return self._get_decorater_name(node.func)
        else:
            logger.warning("Unable to resolve decorator name: %s", ast.dump(node))
            return None

    def visit_Call(self, node: ast.Call) -> None:
        """
        The core visitor. Extracts receiver, method,
        positional args, and kwargs from each call site.
        """
        if isinstance(node.func, ast.Name):
            receiver = None
            method = node.func.id
        elif isinstance(node.func, ast.Attribute):
            receiver = self._get_receiver_name(node.func.value)
            method = node.func.attr
        else:
            return
        
        self.calls.append(
            CallIR(
                receiver=receiver,
                method=method,
                args_count=len(node.args),
                kwargs=[kw.arg for kw in node.keywords if kw.arg is not None],
                context=self._context_stack[-1] if self._context_stack else [],
            )
        )
        self.generic_visit(node)

    def _get_receiver_name(self, node: ast.expr) -> str | None:
        """
        Safely resolves the receiver of an attribute call.
        e.g. for `litellm.completion`, extracts "litellm".
        Returns None if the receiver is too complex to resolve statically.
        """
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return self._get_receiver_name(node.value)
        else:
            return None
