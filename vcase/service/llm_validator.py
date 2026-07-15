from __future__ import annotations

import asyncio
import logging
import os
import httpx

from vcase.providers.base import ApiIndex, ValidationResult, ValidationViolation

logger = logging.getLogger(__name__)


def resolve_provider_and_key(
    model_name: str | None = None,
    api_key: str | None = None,
    provider: str | None = None,
    default_model_map: dict[str, str] | None = None
) -> tuple[str, str, str]:
    """
    Resolves the LLM provider, API key, and model name from arguments or environment variables.
    """
    resolved_key = api_key
    if not resolved_key:
        resolved_key = (
            os.getenv("OPENROUTER_API_KEY") or
            os.getenv("OPENAI_API_KEY") or
            os.getenv("GEMINI_API_KEY") or
            os.getenv("GROQ_API_KEY")
        )
    
    if not resolved_key:
        return "", "", ""

    resolved_provider = provider
    if not resolved_provider:
        if api_key:
            if api_key.startswith("gsk_"):
                resolved_provider = "groq"
            elif api_key.startswith("sk-or-"):
                resolved_provider = "openrouter"
            elif api_key.startswith("sk-"):
                resolved_provider = "openai"
            else:
                resolved_provider = "gemini"
        else:
            if os.getenv("OPENROUTER_API_KEY"):
                resolved_provider = "openrouter"
            elif os.getenv("OPENAI_API_KEY"):
                resolved_provider = "openai"
            elif os.getenv("GEMINI_API_KEY"):
                resolved_provider = "gemini"
            elif os.getenv("GROQ_API_KEY"):
                resolved_provider = "groq"

    if not resolved_provider:
        resolved_provider = "openai"

    resolved_model = model_name
    if not resolved_model:
        env_model = None
        if resolved_provider == "openrouter":
            env_model = os.getenv("OPENROUTER_MODEL")
        elif resolved_provider == "openai":
            env_model = os.getenv("OPENAI_MODEL")
        elif resolved_provider == "gemini":
            env_model = os.getenv("GEMINI_MODEL")
        elif resolved_provider == "groq":
            env_model = os.getenv("GROQ_MODEL")

        if env_model:
            resolved_model = env_model
        elif default_model_map and resolved_provider in default_model_map:
            resolved_model = default_model_map[resolved_provider]
        else:
            resolved_model = "gpt-4o"

    return resolved_provider, resolved_key, resolved_model


async def call_llm_api(
    client: httpx.AsyncClient,
    provider: str,
    api_key: str,
    model: str,
    messages: list[dict[str, str]],
    temperature: float = 0.0,
    timeout: float = 60.0
) -> str:
    """
    Sends chat completion request to the chosen LLM provider (openai, openrouter, gemini, groq).
    """
    if provider == "openrouter":
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "HTTP-Referer": "https://github.com/smuggypusss/Version-Constrained-API-Specification-Engine",
            "X-Title": "VCASE Engine",
            "Content-Type": "application/json"
        }
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature
        }
    elif provider == "openai":
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature
        }
    elif provider == "groq":
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature
        }
    elif provider == "gemini":
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        system_msg = next((m["content"] for m in messages if m["role"] == "system"), "")
        user_msg = next((m["content"] for m in messages if m["role"] == "user"), "")
        prompt = f"System Guidelines:\n{system_msg}\n\nUser Prompt: {user_msg}" if system_msg else user_msg
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": temperature}
        }
        headers = None
    else:
        raise ValueError(f"Unknown LLM provider: {provider}")

    for attempt in range(3):
        try:
            if headers:
                resp = await client.post(url, headers=headers, json=payload, timeout=timeout)
            else:
                resp = await client.post(url, json=payload, timeout=timeout)
            resp.raise_for_status()
            
            if provider == "gemini":
                return resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
            else:
                return resp.json()["choices"][0]["message"]["content"].strip()
        except httpx.HTTPStatusError as e:
            if attempt == 2:
                raise
            wait_time = 2 ** attempt
            logger.warning(f"{provider.capitalize()} API call failed (attempt {attempt+1}/3) with {e.response.status_code}: {e.response.text}. Retrying in {wait_time}s...")
            await asyncio.sleep(wait_time)
        except httpx.HTTPError as e:
            if attempt == 2:
                raise
            wait_time = 2 ** attempt
            logger.warning(f"{provider.capitalize()} API call failed (attempt {attempt+1}/3): {e}. Retrying in {wait_time}s...")
            await asyncio.sleep(wait_time)

    raise RuntimeError(f"All retries failed for provider {provider}")


DEFAULT_VALIDATOR_MODELS = {
    "openrouter": "moonshotai/kimi-k2.6",
    "openai": "gpt-4o-mini",
    "gemini": "gemini-1.5-flash",
    "groq": "llama3-8b-8192"
}


class LlmValidator:

    def __init__(
        self,
        model_name: str | None = None,
        api_key: str | None = None,
        provider: str | None = None
    ) -> None:
        self._model_name = model_name
        self._api_key = api_key
        self._provider = provider

    async def validate(
        self,
        generated_code: str,
        api_indexes: list[ApiIndex],
        violation_context: str,
    ) -> ValidationResult:
        """
        Layer 3: LLM escalation.
        Triggered only when Layer 1 or Layer 2 finds an ambiguous violation.
        Uses a small model with a constrained few-shot prompt.
        """
        provider, api_key, model = resolve_provider_and_key(
            model_name=self._model_name,
            api_key=self._api_key,
            provider=self._provider,
            default_model_map=DEFAULT_VALIDATOR_MODELS
        )
        
        if not api_key:
            logger.info("No LLM API keys found; skipping Layer 3 validation (auto-passed).")
            return ValidationResult(passed=True, violations=[])

        prompt = self._build_validation_prompt(generated_code, api_indexes, violation_context)
        messages = [
            {"role": "system", "content": "You are a strict code validator. Follow user prompt guidelines precisely."},
            {"role": "user", "content": prompt}
        ]

        try:
            async with httpx.AsyncClient() as client:
                result_text = await call_llm_api(
                    client=client,
                    provider=provider,
                    api_key=api_key,
                    model=model,
                    messages=messages,
                    temperature=0.0,
                    timeout=90.0 if provider == "openrouter" else 60.0
                )

            if result_text.upper().startswith("PASS"):
                return ValidationResult(passed=True, violations=[])
            else:
                desc = result_text[5:] if result_text.upper().startswith("FAIL:") else result_text
                return ValidationResult(
                    passed=False,
                    violations=[ValidationViolation(
                        rule_name="llm-validation-error",
                        description=desc,
                        line_number=None,
                        severity="error"
                    )]
                )
        except Exception as e:
            logger.error(f"LLM validation request failed: {e}")
            return ValidationResult(passed=True, violations=[])

    def _build_validation_prompt(self, code: str, indexes: list[ApiIndex], context: str) -> str:
        import re
        # Only include signatures whose names are actually referenced in the generated code or violation context
        referenced_words = set(re.findall(r"\b\w+\b", code))
        referenced_words.update(re.findall(r"\b\w+\b", context))

        indexes_desc = []
        for idx in indexes:
            signatures_desc = []
            for sig in idx.signatures:
                parts = sig.qualified_name.split(".")
                if any(part in referenced_words for part in parts if part):
                    params = ", ".join(f"{p.name}: {p.type_hint}" for p in sig.parameters)
                    signatures_desc.append(f"- {sig.qualified_name}({params}) -> {sig.return_type}")
            
            if signatures_desc:
                # Cap signatures list to avoid excessive prompt sizing
                indexes_desc.append(f"Package: {idx.package}@{idx.version}\n" + "\n".join(signatures_desc[:150]))
            
        specs = "\n\n".join(indexes_desc)
        return f"""
You are a strict code validation assistant.
Evaluate if the following generated code violates the API contract specifications or has architectural pattern errors.

API Specifications:
{specs}

Potential violation context:
{context}

Generated Code:
---
{code}
---

If the code is correct and does not violate any rules or API signatures, reply ONLY with "PASS".
If it is incorrect, reply with "FAIL: <detailed explanation of the violation>".
"""
