from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
import httpx

from vcase.providers.base import ApiIndex, ResolvedDependency, TechnologyPattern, ValidationViolation
from vcase.service.detector import TechnologyDetector
from vcase.service.resolver import DependencyResolver
from vcase.service.retriever import DocumentationRetriever
from vcase.service.spec_builder import SpecBuilder
from vcase.service.api_validator import ApiValidator
from vcase.service.architecture_validator import ArchitectureValidator
from vcase.service.llm_validator import LlmValidator
from vcase.service.interaction_graph import get_constraints_for, get_active_patterns

logger = logging.getLogger(__name__)

MAX_RETRY_ATTEMPTS = 3


class Orchestrator:

    def __init__(
        self,
        detector: TechnologyDetector,
        resolver: DependencyResolver,
        retriever: DocumentationRetriever,
        spec_builder: SpecBuilder,
        api_validator: ApiValidator,
        architecture_validator: ArchitectureValidator,
        llm_validator: LlmValidator,
        model_name: str | None = None,
        api_key: str | None = None,
        provider: str | None = None
    ) -> None:
        self._detector = detector
        self._resolver = resolver
        self._retriever = retriever
        self._spec_builder = spec_builder
        self._api_validator = api_validator
        self._architecture_validator = architecture_validator
        self._llm_validator = llm_validator
        self._model_name = model_name
        self._api_key = api_key
        self._provider = provider

    async def run(self, prompt: str, repo_path: Path, target_file: Path | None = None) -> str:
        """
        Full pipeline coordinator.
        1. Detect ecosystems and technologies.
        2. Resolve dependency versions (three-tier).
        3. Retrieve and extract API contracts.
        4. Load interaction patterns for the detected tech stack.
        5. Build enforcement system prompt.
        6. Call LLM.
        7. Validate output (Layer 1 → Layer 2 → Layer 3 if needed).
        8. Retry on violation up to MAX_RETRY_ATTEMPTS.
        9. Return validated code or raise with violation detail.
        """
        # 1. Detect technologies in prompt & ecosystems
        techs = self._detector.detect_technologies_in_prompt(prompt)
        
        # 2. Resolve dependencies
        logger.info(f"Resolving dependencies for repository at {repo_path}")
        resolved_deps = await self._resolver.resolve(repo_path)
        for dep in resolved_deps:
            if dep.name not in techs:
                techs.append(dep.name)

        # 3. Retrieve API contracts
        api_indexes = []
        for dep in resolved_deps:
            logger.info(f"Retrieving API index for dependency: {dep.name}")
            idx = await self._retriever.retrieve(dep)
            if idx:
                api_indexes.append(idx)

        # Scan local codebase module signatures
        logger.info(f"Scanning workspace for internal module signatures...")
        from vcase.service.workspace_scanner import WorkspaceScanner
        scanner = WorkspaceScanner()
        workspace_idx, local_modules = scanner.scan(repo_path)
        if workspace_idx and workspace_idx.signatures:
            api_indexes.append(workspace_idx)

        # 4. Load interaction patterns and constraints
        patterns = get_active_patterns(techs)
        constraints = []
        for tech in techs:
            constraints.extend(get_constraints_for(tech))

        # 5-8. Orchestrate generation & validation loop
        previous_violations: list[ValidationViolation] = []
        for attempt in range(1, MAX_RETRY_ATTEMPTS + 1):
            logger.info(f"Code generation attempt {attempt}/{MAX_RETRY_ATTEMPTS}")
            
            # Build enforcement system prompt
            system_prompt = self._spec_builder.build_system_prompt(api_indexes, patterns, user_prompt=prompt)
            
            # Inject target file contents if specified and exists
            prompt_context = prompt
            if target_file:
                target_file_path = repo_path / target_file if not target_file.is_absolute() else target_file
                if target_file_path.exists():
                    try:
                        content = target_file_path.read_text(encoding="utf-8")
                        prompt_context = f"Target File to edit: {target_file.name}\nExisting content:\n```python\n{content}\n```\n\nInstructions:\n{prompt}"
                        system_prompt += f"\n\nYou are editing {target_file.name}. Please output the full updated code including your changes."
                    except Exception as e:
                        logger.warning(f"Could not read target file {target_file_path}: {e}")
            
            if previous_violations:
                violation_text = "\n".join(f"- [{v.rule_name}]: {v.description}" for v in previous_violations)
                system_prompt += f"\n\n## PREVIOUS ATTEMPT VIOLATIONS (CRITICAL - YOU MUST FIX THESE):\n{violation_text}"

            # Call LLM
            generated_code = await self._call_llm(system_prompt, prompt_context)

            # Validate generated code
            api_res = self._api_validator.validate(
                generated_code, api_indexes, extra_whitelisted_imports=local_modules,
                resolved_dep_names=[dep.name for dep in resolved_deps]
            )
            arch_res = self._architecture_validator.validate(generated_code, patterns, constraints)

            violations = api_res.violations + arch_res.violations

            # Layer 3 escalation if violations exist and need LLM evaluation (optional fallback check)
            if violations and (os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY") or os.getenv("GEMINI_API_KEY")):
                # Call LLM validator to verify if violations are genuine
                violation_ctx = "; ".join(f"[{v.rule_name}] {v.description}" for v in violations)
                llm_res = await self._llm_validator.validate(generated_code, api_indexes, violation_ctx)
                if llm_res.passed:
                    logger.info("Layer 3 LLM Validator overruled static analysis violations (passed).")
                    violations = []
                else:
                    violations = llm_res.violations

            errors = [v for v in violations if v.severity == "error"]
            if not errors:
                logger.info("Validation passed successfully.")
                return generated_code

            logger.warning(f"Attempt {attempt} failed validation with errors: {errors}")
            previous_violations = errors

        # If we reached here, validation failed after MAX_RETRY_ATTEMPTS
        error_details = "; ".join(f"[{v.rule_name}] {v.description}" for v in previous_violations)
        raise ValueError(f"Code validation failed after {MAX_RETRY_ATTEMPTS} attempts. Violations: {error_details}")

    async def _call_llm(self, system_prompt: str, user_prompt: str) -> str:
        """Helper to invoke OpenAI, Gemini, or OpenRouter APIs, falling back to deterministic mock generators."""
        from vcase.service.llm_validator import resolve_provider_and_key, call_llm_api
        
        provider, api_key, model = resolve_provider_and_key(
            model_name=self._model_name,
            api_key=self._api_key,
            provider=self._provider,
            default_model_map={
                "openrouter": "moonshotai/kimi-k2.6",
                "openai": "gpt-4o",
                "gemini": "gemini-1.5-flash",
                "groq": "llama3-8b-8192"
            }
        )

        if not api_key:
            logger.info("No LLM API keys found; generating mock code.")
            user_prompt_lower = user_prompt.lower()
            if "temporal" in user_prompt_lower and "fastapi" in user_prompt_lower:
                # Returns a correct FastAPI + Temporal pattern code block
                return """from fastapi import FastAPI
from temporalio.client import Client

app = FastAPI()

@app.post("/workflow")
async def run_workflow():
    client = await Client.connect("localhost:7233")
    await client.start_workflow("MyWorkflow", id="wf-1", task_queue="queue")
    return {"status": "started"}
"""
            elif "litellm" in user_prompt_lower:
                return """import litellm

res = litellm.completion(
    model="gpt-4o",
    messages=[{"role": "user", "content": "test"}]
)
"""
            return "# Mock Generated Code\npass"

        try:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            async with httpx.AsyncClient() as client:
                return await call_llm_api(
                    client=client,
                    provider=provider,
                    api_key=api_key,
                    model=model,
                    messages=messages,
                    temperature=0.2,
                    timeout=90.0 if provider == "openrouter" else 60.0
                )
        except Exception as e:
            logger.error(f"LLM API generation call failed after retries: {e}")
            raise RuntimeError(f"LLM API generation call failed after retries: {e}")

