from __future__ import annotations

import logging
from pathlib import Path
import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from vcase import create_orchestrator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["proxy"])


class ProxyRequest(BaseModel):
    prompt: str = Field(..., min_length=1)
    repo_path: str = Field(..., min_length=1)
    model: str | None = Field(default=None, description="Optional custom LLM model name")
    api_key: str | None = Field(default=None, description="Optional custom API key for the model/provider")
    provider: str | None = Field(default=None, description="Optional provider: openai, gemini, openrouter, groq")


class ProxyResponse(BaseModel):
    code: str
    resolved_dependencies: list[dict]
    validation_passed: bool
    violations: list[dict]


class ContextRequest(BaseModel):
    prompt: str = Field(..., min_length=1)
    repo_path: str = Field(..., min_length=1)


class ContextResponse(BaseModel):
    context_prompt: str
    resolved_dependencies: list[dict]


class ValidateRequest(BaseModel):
    code: str = Field(..., min_length=1)
    repo_path: str = Field(..., min_length=1)


class ValidateResponse(BaseModel):
    passed: bool
    violations: list[dict]


@router.post("/generate", response_model=ProxyResponse)
async def generate(request: ProxyRequest) -> ProxyResponse:
    """
    Orchestration proxy endpoint.
    Accepts a user prompt and a local repo path.
    Returns validated, version-accurate generated code.
    """
    repo_path = Path(request.repo_path)
    if not repo_path.exists():
        raise HTTPException(status_code=400, detail=f"Repository path '{request.repo_path}' does not exist.")

    async with httpx.AsyncClient() as http_client:
        orchestrator = create_orchestrator(
            http_client,
            model_name=request.model,
            api_key=request.api_key,
            provider=request.provider
        )

        # Pre-resolve dependencies for the response payload
        try:
            resolved_deps = await orchestrator._resolver.resolve(repo_path)
            resolved_dicts = [
                {
                    "name": d.name,
                    "version": d.version,
                    "ecosystem": d.ecosystem.value,
                    "resolution_tier": d.resolution_tier.name
                }
                for d in resolved_deps
            ]
        except Exception as e:
            logger.exception("Dependency resolution failed")
            raise HTTPException(status_code=500, detail=f"Dependency resolution failed: {e}")

        # Run pipeline Orchestrator loop
        try:
            code = await orchestrator.run(request.prompt, repo_path)
            return ProxyResponse(
                code=code,
                resolved_dependencies=resolved_dicts,
                validation_passed=True,
                violations=[]
            )
        except ValueError as e:
            return ProxyResponse(
                code="",
                resolved_dependencies=resolved_dicts,
                validation_passed=False,
                violations=[{"rule_name": "validation-failure", "description": str(e)}]
            )
        except Exception as e:
            logger.exception("Code generation orchestration failed")
            raise HTTPException(status_code=500, detail=f"Code generation orchestration failed: {e}")


@router.post("/context", response_model=ContextResponse)
async def get_context(request: ContextRequest) -> ContextResponse:
    """
    Context Retrieval Endpoint.
    Accepts a prompt and repo_path, and returns versioned specification guidelines.
    """
    repo_path = Path(request.repo_path)
    if not repo_path.exists():
        raise HTTPException(status_code=400, detail=f"Repository path '{request.repo_path}' does not exist.")

    async with httpx.AsyncClient() as http_client:
        orchestrator = create_orchestrator(http_client)
        
        # 1. Detect technologies
        techs = orchestrator._detector.detect_technologies_in_prompt(request.prompt)
        
        # 2. Resolve dependencies
        try:
            resolved_deps = await orchestrator._resolver.resolve(repo_path)
            for dep in resolved_deps:
                if dep.name not in techs:
                    techs.append(dep.name)
            
            resolved_dicts = [
                {
                    "name": d.name,
                    "version": d.version,
                    "ecosystem": d.ecosystem.value,
                    "resolution_tier": d.resolution_tier.name
                }
                for d in resolved_deps
            ]
        except Exception as e:
            logger.exception("Dependency resolution failed")
            raise HTTPException(status_code=500, detail=f"Dependency resolution failed: {e}")

        # 3. Retrieve signatures
        api_indexes = []
        for dep in resolved_deps:
            idx = await orchestrator._retriever.retrieve(dep)
            if idx:
                api_indexes.append(idx)

        # 4. Scan workspace
        from vcase.service.workspace_scanner import WorkspaceScanner
        scanner = WorkspaceScanner()
        workspace_idx, _ = scanner.scan(repo_path)
        if workspace_idx and workspace_idx.signatures:
            api_indexes.append(workspace_idx)

        # 5. Load patterns and constraints
        from vcase.service.interaction_graph import get_active_patterns
        patterns = get_active_patterns(techs)

        # 6. Build system prompt
        context_prompt = orchestrator._spec_builder.build_system_prompt(
            api_indexes, patterns, user_prompt=request.prompt
        )

        return ContextResponse(
            context_prompt=context_prompt,
            resolved_dependencies=resolved_dicts
        )


@router.post("/validate", response_model=ValidateResponse)
async def validate_code(request: ValidateRequest) -> ValidateResponse:
    """
    Code Validation Endpoint.
    Lints user-supplied code against dependency signatures and architectural rules.
    """
    repo_path = Path(request.repo_path)
    if not repo_path.exists():
        raise HTTPException(status_code=400, detail=f"Repository path '{request.repo_path}' does not exist.")

    async with httpx.AsyncClient() as http_client:
        orchestrator = create_orchestrator(http_client)

        # 1. Resolve dependencies
        try:
            resolved_deps = await orchestrator._resolver.resolve(repo_path)
            techs = [dep.name for dep in resolved_deps]
        except Exception as e:
            logger.exception("Dependency resolution failed")
            raise HTTPException(status_code=500, detail=f"Dependency resolution failed: {e}")

        # 2. Retrieve signatures
        api_indexes = []
        for dep in resolved_deps:
            idx = await orchestrator._retriever.retrieve(dep)
            if idx:
                api_indexes.append(idx)

        # 3. Scan workspace
        from vcase.service.workspace_scanner import WorkspaceScanner
        scanner = WorkspaceScanner()
        workspace_idx, local_modules = scanner.scan(repo_path)
        if workspace_idx and workspace_idx.signatures:
            api_indexes.append(workspace_idx)

        # 4. Load constraints
        from vcase.service.interaction_graph import get_constraints_for, get_active_patterns
        patterns = get_active_patterns(techs)
        constraints = []
        for tech in techs:
            constraints.extend(get_constraints_for(tech))

        # 5. Validate
        api_res = orchestrator._api_validator.validate(
            request.code, api_indexes, extra_whitelisted_imports=local_modules
        )
        arch_res = orchestrator._architecture_validator.validate(
            request.code, patterns, constraints
        )

        violations = api_res.violations + arch_res.violations

        # Format violations as dict lists
        violations_dicts = [
            {
                "rule_name": v.rule_name,
                "description": v.description,
                "line_number": v.line_number,
                "severity": v.severity
            }
            for v in violations
        ]
        
        has_error = any(v["severity"] == "error" for v in violations_dicts)

        return ValidateResponse(
            passed=not has_error,
            violations=violations_dicts
        )

