from __future__ import annotations

from pathlib import Path

from vcase.validator.core.ir import CodeFileIR


class TypeScriptAdapter:
    """
    Future adapter for TypeScript/JavaScript source files.

    Will use Babel or the TypeScript Compiler API (via a subprocess call)
    to produce a normalized CodeFileIR identical in structure to the Python adapter.

    This class is a stub. The Python adapter must be stable before this is built.
    """

    def parse(self, filepath: Path) -> CodeFileIR:
        """
        Entry point. Will invoke the TypeScript parser and produce a CodeFileIR.
        The output structure is identical to PythonAdapter.parse().
        """
        raise NotImplementedError("TypeScript adapter is not yet implemented.")
