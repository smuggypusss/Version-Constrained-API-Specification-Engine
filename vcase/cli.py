from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path
import httpx
import uvicorn
from dotenv import load_dotenv

from vcase import create_orchestrator


def main() -> None:
    # Load environment variables
    load_dotenv(override=True)
    parser = argparse.ArgumentParser(
        description="Version-Constrained API Specification Engine (VCASE)"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # serve command
    serve_parser = subparsers.add_parser("serve", help="Start the VCASE FastAPI server")
    serve_parser.add_argument("--host", default="127.0.0.1", help="Host binding address")
    serve_parser.add_argument("--port", type=int, default=8000, help="Port to listen on")
    serve_parser.add_argument("--reload", action="store_true", help="Enable hot reloading")

    # run command
    run_parser = subparsers.add_parser("run", help="Generate and validate code directly from the CLI")
    run_parser.add_argument("--prompt", required=True, help="User instructions / prompt")
    run_parser.add_argument("--repo-path", required=True, help="Path to local repository to inspect stack/versions")
    run_parser.add_argument("--target-file", help="Optional relative path to target file to generate/edit")
    run_parser.add_argument("--api-key", help="API key for the selected LLM provider")
    run_parser.add_argument("--model", help="Model name to use for generation and validation")
    run_parser.add_argument("--provider", choices=["openai", "gemini", "openrouter", "groq"], help="LLM API provider")

    # context command
    context_parser = subparsers.add_parser("context", help="Retrieve versioned specification context for code generation")
    context_parser.add_argument("--prompt", required=True, help="User prompt or instructions")
    context_parser.add_argument("--repo-path", required=True, help="Path to local repository to inspect stack/versions")

    # validate command
    validate_parser = subparsers.add_parser("validate", help="Validate/lint code against dependency contracts and rules")
    validate_parser.add_argument("--code-file", required=True, help="Path to Python file containing code to validate")
    validate_parser.add_argument("--repo-path", required=True, help="Path to local repository")

    args = parser.parse_args()

    if args.command == "serve":
        print(f"Starting VCASE API proxy server on http://{args.host}:{args.port}...")
        # Since uvicorn.run expects target app, we pass the package module target path
        uvicorn.run("vcase.main:app", host=args.host, port=args.port, reload=args.reload)
        
    elif args.command == "run":
        repo_path = Path(args.repo_path)
        if not repo_path.exists():
            print(f"Error: Repository path '{args.repo_path}' does not exist.", file=sys.stderr)
            sys.exit(1)

        async def run_pipeline():
            async with httpx.AsyncClient() as http_client:
                orchestrator = create_orchestrator(
                    http_client,
                    model_name=args.model,
                    api_key=args.api_key,
                    provider=args.provider
                )
                try:
                    # Execute orchestrator pipeline
                    target_file = Path(args.target_file) if args.target_file else None
                    code = await orchestrator.run(args.prompt, repo_path, target_file=target_file)
                    print("\n--- GENERATED & VALIDATED CODE ---")
                    print(code)
                    print("----------------------------------\n")
                    print("Status: Validation Passed.")
                    
                    if target_file:
                        target_file_path = repo_path / target_file if not target_file.is_absolute() else target_file
                        # Ensure directories exist
                        target_file_path.parent.mkdir(parents=True, exist_ok=True)
                        target_file_path.write_text(code, encoding="utf-8")
                        print(f"Saved generated code directly to: {target_file_path}")
                except ValueError as e:
                    print(f"\nValidation Failed:\n{e}", file=sys.stderr)
                    sys.exit(2)
                except Exception as e:
                    print(f"\nOrchestrator Execution Failed:\n{e}", file=sys.stderr)
                    sys.exit(3)

        asyncio.run(run_pipeline())

    elif args.command == "context":
        repo_path = Path(args.repo_path)
        if not repo_path.exists():
            print(f"Error: Repository path '{args.repo_path}' does not exist.", file=sys.stderr)
            sys.exit(1)

        async def get_context():
            async with httpx.AsyncClient() as http_client:
                orchestrator = create_orchestrator(http_client)
                try:
                    techs = orchestrator._detector.detect_technologies_in_prompt(args.prompt)
                    resolved_deps = await orchestrator._resolver.resolve(repo_path)
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
                    workspace_idx, _ = scanner.scan(repo_path)
                    if workspace_idx and workspace_idx.signatures:
                        api_indexes.append(workspace_idx)

                    from vcase.service.interaction_graph import get_active_patterns
                    patterns = get_active_patterns(techs)

                    context_prompt = orchestrator._spec_builder.build_system_prompt(
                        api_indexes, patterns, user_prompt=args.prompt
                    )
                    print(context_prompt)
                except Exception as e:
                    print(f"Error gathering context: {e}", file=sys.stderr)
                    sys.exit(1)

        asyncio.run(get_context())

    elif args.command == "validate":
        repo_path = Path(args.repo_path)
        code_file = Path(args.code_file)
        if not repo_path.exists():
            print(f"Error: Repository path '{args.repo_path}' does not exist.", file=sys.stderr)
            sys.exit(1)
        if not code_file.exists():
            print(f"Error: Code file '{args.code_file}' does not exist.", file=sys.stderr)
            sys.exit(1)

        async def run_validation():
            async with httpx.AsyncClient() as http_client:
                orchestrator = create_orchestrator(http_client)
                try:
                    code = code_file.read_text(encoding="utf-8")
                    resolved_deps = await orchestrator._resolver.resolve(repo_path)
                    techs = [dep.name for dep in resolved_deps]

                    api_indexes = []
                    for dep in resolved_deps:
                        idx = await orchestrator._retriever.retrieve(dep)
                        if idx:
                            api_indexes.append(idx)

                    # Scan workspace
                    from vcase.service.workspace_scanner import WorkspaceScanner
                    scanner = WorkspaceScanner()
                    workspace_idx, local_modules = scanner.scan(repo_path)
                    if workspace_idx and workspace_idx.signatures:
                        api_indexes.append(workspace_idx)

                    from vcase.service.interaction_graph import get_constraints_for, get_active_patterns
                    patterns = get_active_patterns(techs)
                    constraints = []
                    for tech in techs:
                        constraints.extend(get_constraints_for(tech))

                    api_res = orchestrator._api_validator.validate(
                        code, api_indexes, extra_whitelisted_imports=local_modules
                    )
                    arch_res = orchestrator._architecture_validator.validate(
                        code, patterns, constraints
                    )

                    violations = api_res.violations + arch_res.violations
                    errors = [v for v in violations if v.severity == "error"]
                    warnings = [v for v in violations if v.severity == "warning"]

                    if violations:
                        print(f"Validation failed with {len(errors)} errors and {len(warnings)} warnings:", file=sys.stderr)
                        for v in violations:
                            print(f"- [{v.severity.upper()}] [{v.rule_name}]: {v.description}", file=sys.stderr)
                        sys.exit(2)
                    else:
                        print("Validation passed successfully! No contract violations found.")
                except Exception as e:
                    print(f"Error running validation: {e}", file=sys.stderr)
                    sys.exit(3)

        asyncio.run(run_validation())


if __name__ == "__main__":
    main()
