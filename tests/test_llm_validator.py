from __future__ import annotations

import os
from unittest.mock import AsyncMock, patch
import pytest
import httpx

from vcase.service.llm_validator import LlmValidator
from vcase.providers.base import ApiIndex, ApiSignature, ApiParameter


class TestLlmValidatorOpenRouter:

    @pytest.mark.asyncio
    @patch.dict(os.environ, {
        "OPENROUTER_API_KEY": "sk-or-v1-test-key",
        "OPENAI_API_KEY": "",
        "GEMINI_API_KEY": ""
    })
    async def test_validate_calls_openrouter_correctly(self) -> None:
        validator = LlmValidator("moonshotai/kimi-k2.6")
        
        # Mocking the response of httpx client post call
        mock_response = httpx.Response(
            status_code=200,
            json={"choices": [{"message": {"content": "PASS"}}]}
        )
        
        # We patch httpx.AsyncClient.post
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            
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
            
            result = await validator.validate(
                generated_code="import litellm\nlitellm.completion(model='gpt-4o')",
                api_indexes=api_indexes,
                violation_context="[api-invalid-kwargs] test violation"
            )
            
            assert result.passed is True
            assert len(result.violations) == 0
            
            # Verify the call payload
            mock_post.assert_called_once()
            called_url = mock_post.call_args[0][0]
            called_kwargs = mock_post.call_args[1]
            
            assert called_url == "https://openrouter.ai/api/v1/chat/completions"
            assert called_kwargs["headers"]["Authorization"] == "Bearer sk-or-v1-test-key"
            assert called_kwargs["headers"]["HTTP-Referer"] == "https://github.com/smuggypusss/Version-Constrained-API-Specification-Engine"
            assert called_kwargs["json"]["model"] == "moonshotai/kimi-k2.6"
            assert "You are a strict code validator" in called_kwargs["json"]["messages"][0]["content"]
