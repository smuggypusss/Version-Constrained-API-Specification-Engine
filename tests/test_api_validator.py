from __future__ import annotations

import pytest

from vcase.service.api_validator import ApiValidator
from vcase.providers.base import ApiIndex, ApiSignature, ApiParameter


class TestApiValidator:

    def test_passes_when_all_calls_exist_in_index(self) -> None:
        validator = ApiValidator()
        code = "import litellm\nlitellm.completion(model='gpt-4o', messages=[])"
        api_indexes = [
            ApiIndex(
                package="litellm",
                version="1.40.0",
                signatures=(
                    ApiSignature(
                        qualified_name="litellm.completion",
                        parameters=(
                            ApiParameter(name="model", type_hint="str", required=True, description=""),
                            ApiParameter(name="messages", type_hint="list", required=True, description="")
                        ),
                        return_type="ModelResponse",
                        available_since="",
                        deprecated=False
                    ),
                )
            )
        ]
        result = validator.validate(code, api_indexes)
        assert result.passed is True
        assert len(result.violations) == 0

    def test_flags_call_not_present_in_api_index(self) -> None:
        validator = ApiValidator()
        code = "import litellm\nlitellm.non_existent(model='gpt-5-mini')"
        api_indexes = [
            ApiIndex(
                package="litellm",
                version="1.40.0",
                signatures=()
            )
        ]
        result = validator.validate(code, api_indexes)
        assert result.passed is False
        assert any(v.rule_name == "api-unknown" for v in result.violations)

    def test_flags_deprecated_api_usage(self) -> None:
        validator = ApiValidator()
        code = "import litellm\nlitellm.completion(model='gpt-4o')"
        api_indexes = [
            ApiIndex(
                package="litellm",
                version="1.40.0",
                signatures=(
                    ApiSignature(
                        qualified_name="litellm.completion",
                        parameters=(ApiParameter(name="model", type_hint="str", required=True, description=""),),
                        return_type="ModelResponse",
                        available_since="",
                        deprecated=True,
                        deprecation_note="Use acompletion instead."
                    ),
                )
            )
        ]
        result = validator.validate(code, api_indexes)
        assert result.passed is True
        assert any(v.rule_name == "api-deprecated" for v in result.violations)

    def test_returns_empty_violations_for_empty_code(self) -> None:
        validator = ApiValidator()
        result = validator.validate("", [])
        assert result.passed is True
        assert len(result.violations) == 0

    def test_passes_with_arbitrary_kwargs_when_signature_has_kwargs(self) -> None:
        validator = ApiValidator()
        code = "import litellm\nlitellm.completion(model='gpt-4o', messages=[], custom_kwarg=123)"
        api_indexes = [
            ApiIndex(
                package="litellm",
                version="1.40.0",
                signatures=(
                    ApiSignature(
                        qualified_name="litellm.completion",
                        parameters=(
                            ApiParameter(name="model", type_hint="str", required=True, description=""),
                            ApiParameter(name="**kwargs", type_hint="Any", required=False, description=""),
                        ),
                        return_type="ModelResponse",
                        available_since="",
                        deprecated=False
                    ),
                )
            )
        ]
        result = validator.validate(code, api_indexes)
        assert result.passed is True
        assert len(result.violations) == 0

    def test_passes_with_markdown_code_fences(self) -> None:
        validator = ApiValidator()
        code = "```python\nimport litellm\nlitellm.completion(model='gpt-4o')\n```"
        api_indexes = [
            ApiIndex(
                package="litellm",
                version="1.40.0",
                signatures=(
                    ApiSignature(
                        qualified_name="litellm.completion",
                        parameters=(
                            ApiParameter(name="model", type_hint="str", required=True, description=""),
                        ),
                        return_type="ModelResponse",
                        available_since="",
                        deprecated=False
                    ),
                )
            )
        ]
        result = validator.validate(code, api_indexes)
        assert result.passed is True
        assert len(result.violations) == 0

    def test_excludes_standard_library_imports_and_calls(self) -> None:
        validator = ApiValidator()
        code = "import json\nimport sys\njson.dumps({'a': 1})\nsys.exit(0)"
        result = validator.validate(code, [], resolved_dep_names=[])
        assert result.passed is True
        assert len(result.violations) == 0

    def test_resolves_aliased_module_imports(self) -> None:
        validator = ApiValidator()
        code = "import litellm as llm\nllm.completion(model='gpt-4o')"
        api_indexes = [
            ApiIndex(
                package="litellm",
                version="1.40.0",
                signatures=(
                    ApiSignature(
                        qualified_name="litellm.completion",
                        parameters=(
                            ApiParameter(name="model", type_hint="str", required=True, description=""),
                        ),
                        return_type="ModelResponse",
                        available_since="",
                        deprecated=False
                    ),
                )
            )
        ]
        result = validator.validate(code, api_indexes, resolved_dep_names=["litellm"])
        assert result.passed is True
        assert len(result.violations) == 0

    def test_resolves_aliased_from_imports(self) -> None:
        validator = ApiValidator()
        code = "from litellm import completion as comp\ncomp(model='gpt-4o')"
        api_indexes = [
            ApiIndex(
                package="litellm",
                version="1.40.0",
                signatures=(
                    ApiSignature(
                        qualified_name="litellm.completion",
                        parameters=(
                            ApiParameter(name="model", type_hint="str", required=True, description=""),
                        ),
                        return_type="ModelResponse",
                        available_since="",
                        deprecated=False
                    ),
                )
            )
        ]
        result = validator.validate(code, api_indexes, resolved_dep_names=["litellm"])
        assert result.passed is True
        assert len(result.violations) == 0

    def test_passes_non_dependency_local_receivers(self) -> None:
        validator = ApiValidator()
        # 'logger' is not a known dependency package or standard library receiver, so logger.info should be ignored (no false positive for api-unknown)
        code = "logger.info('hello')"
        result = validator.validate(code, [], resolved_dep_names=[])
        assert result.passed is True
        assert len(result.violations) == 0

    def test_validates_transitive_dependency_imports(self) -> None:
        from unittest.mock import patch
        validator = ApiValidator()
        # Let's say my_dep imports another_dep transitively, so importing another_dep is valid.
        code = "import another_dep"
        
        # Mock importlib.metadata.requires to return dependencies for my_dep
        with patch("importlib.metadata.requires") as mock_requires:
            def side_effect(pkg):
                if pkg == "my_dep":
                    return ["another_dep>=1.0.0"]
                return None
            mock_requires.side_effect = side_effect
            
            result = validator.validate(code, [], resolved_dep_names=["my_dep"])
            assert result.passed is True
            assert len(result.violations) == 0
