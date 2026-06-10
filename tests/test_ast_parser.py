from __future__ import annotations

import tempfile
from pathlib import Path
import pytest

from vcase.service.ast_parser import AstParser


class TestAstParser:

    def test_parses_vararg_and_kwarg_correctly(self) -> None:
        parser = AstParser()
        code = """
def test_func(a, b=1, *args, c=2, **kwargs):
    pass
"""
        with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w", encoding="utf-8") as f:
            f.write(code)
            tmp_path = Path(f.name)

        try:
            api_index = parser.parse_file(package_name="testpkg", package_version="1.0.0", filepath=tmp_path)
            assert api_index.package == "testpkg"
            assert api_index.version == "1.0.0"
            assert len(api_index.signatures) == 1
            sig = api_index.signatures[0]
            assert sig.qualified_name.endswith(".test_func")
            
            param_names = [p.name for p in sig.parameters]
            assert "a" in param_names
            assert "*args" in param_names
            assert "c" in param_names
            assert "**kwargs" in param_names
        finally:
            try:
                tmp_path.unlink()
            except Exception:
                pass
