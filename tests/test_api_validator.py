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
