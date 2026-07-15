from __future__ import annotations

import os
from pathlib import Path
import httpx
from mcp.server.fastmcp import FastMCP
from vcase import create_orchestrator

# Initialize FastMCP server
# The name "vcase" will be the server identifier in the client UI
mcp = FastMCP("vcase")

@mcp.tool()
async def vcase_get_context(prompt: str, repo_path: str) -> str:
    """
    Retrieve versioned system prompts and API signature constraints for a prompt.
    Use this to get context when preparing to generate code in Cursor/LLM.
    
    :param prompt: The instruction or query of what you want to write (e.g. "similarity search with FAISS")
    :param repo_path: Path to the local repository (to scan for requirements.txt, poetry.lock, and workspace code)
    """
    path = Path(repo_path)
    if not path.exists():
        return f"Error: Repository path '{repo_path}' does not exist."

    async with httpx.AsyncClient() as http_client:
        orchestrator = create_orchestrator(http_client)
        try:
            techs = orchestrator._detector.detect_technologies_in_prompt(prompt)
            resolved_deps = await orchestrator._resolver.resolve(path)
            for dep in resolved_deps:
                if dep.name not in techs:
                    techs.append(dep.name)

            api_indexes = []
            for dep in resolved_deps:
                idx = await orchestrator._retriever.retrieve(dep)
                if idx:
                    api_indexes.append(idx)

            # Scan workspace
            from vcase.service.workspace_scanner import WorkspaceScanner
            scanner = WorkspaceScanner()
            workspace_idx, _ = scanner.scan(path)
            if workspace_idx and workspace_idx.signatures:
                api_indexes.append(workspace_idx)

            from vcase.service.interaction_graph import get_active_patterns
            patterns = get_active_patterns(techs)

            context_prompt = orchestrator._spec_builder.build_system_prompt(
                api_indexes, patterns, user_prompt=prompt
            )
            return context_prompt
        except Exception as e:
            return f"Error gathering VCASE context: {e}"


@mcp.tool()
async def vcase_validate_code(code: str, repo_path: str, code_file: str | None = None) -> str:
    """
    Validate/lint Python code against third-party dependency API contracts and architectural constraints.
    Returns all found validation errors or warnings.
    
    :param code: The Python code snippet or full file contents to validate.
    :param repo_path: Path to the local repository containing requirements/lock files.
    :param code_file: Optional filename or relative path of the file containing the code (assists with context).
    """
    path = Path(repo_path)
    if not path.exists():
        return f"Error: Repository path '{repo_path}' does not exist."

    async with httpx.AsyncClient() as http_client:
        orchestrator = create_orchestrator(http_client)
        try:
            resolved_deps = await orchestrator._resolver.resolve(path)
            techs = [dep.name for dep in resolved_deps]

            api_indexes = []
            for dep in resolved_deps:
                idx = await orchestrator._retriever.retrieve(dep)
                if idx:
                    api_indexes.append(idx)

            # Scan workspace
            from vcase.service.workspace_scanner import WorkspaceScanner
            scanner = WorkspaceScanner()
            workspace_idx, local_modules = scanner.scan(path)
            if workspace_idx and workspace_idx.signatures:
                api_indexes.append(workspace_idx)

            from vcase.service.interaction_graph import get_constraints_for, get_active_patterns
            patterns = get_active_patterns(techs)
            constraints = []
            for tech in techs:
                constraints.extend(get_constraints_for(tech))

            api_res = orchestrator._api_validator.validate(
                code, api_indexes, extra_whitelisted_imports=local_modules,
                resolved_dep_names=[dep.name for dep in resolved_deps]
            )
            arch_res = orchestrator._architecture_validator.validate(
                code, patterns, constraints
            )

            violations = api_res.violations + arch_res.violations
            if not violations:
                return "Validation passed successfully! No contract or architectural violations found."

            errors = [v for v in violations if v.severity == "error"]
            warnings = [v for v in violations if v.severity == "warning"]
            
            res = f"Validation failed with {len(errors)} errors and {len(warnings)} warnings:\n"
            for v in violations:
                res += f"- [{v.severity.upper()}] [{v.rule_name}]: {v.description}\n"
            return res
        except Exception as e:
            return f"Error running VCASE validation: {e}"


@mcp.tool()
async def vcase_run_generation(
    prompt: str,
    repo_path: str,
    target_file: str | None = None,
    model: str | None = None,
    provider: str | None = None,
    api_key: str | None = None
) -> str:
    """
    Orchestrate full self-correcting code generation using an LLM.
    Generates code, runs validation, and retries on errors until clean code is produced.
    
    :param prompt: User instructions / prompt of what code to generate.
    :param repo_path: Path to the local repository containing requirements/lock files.
    :param target_file: Optional relative path of the file to save the generated code to.
    :param model: Optional LLM model name (defaults to configured model in .env if not specified).
    :param provider: Optional LLM provider name (e.g. 'openai', 'gemini', 'openrouter', 'groq').
    :param api_key: Optional API key for the selected LLM provider.
    """
    path = Path(repo_path)
    if not path.exists():
        return f"Error: Repository path '{repo_path}' does not exist."

    async with httpx.AsyncClient() as http_client:
        orchestrator = create_orchestrator(
            http_client,
            model_name=model,
            api_key=api_key,
            provider=provider
        )
        try:
            target_path = Path(target_file) if target_file else None
            code = await orchestrator.run(prompt, path, target_file=target_path)
            
            if target_path:
                target_file_path = path / target_path if not target_path.is_absolute() else target_path
                target_file_path.parent.mkdir(parents=True, exist_ok=True)
                target_file_path.write_text(code, encoding="utf-8")
                return f"Successfully generated and validated code. Saved to: {target_file_path}\n\n```python\n{code}\n```"
            return code
        except Exception as e:
            return f"Orchestrator generation failed: {e}"
