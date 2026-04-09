# Version-Constrained API Specification Engine

A deterministic, version-aware knowledge streaming infrastructure for Large Language Models (LLMs). 

## Why does this exist?
When LLMs generate code, they frequently rely on outdated training data or hallucinate API signatures for newer libraries. Traditional Retrieval-Augmented Generation (RAG) is often static and misses critical version-specific nuances or architectural constraints.

This engine replaces static RAG with a **five-layer defense system**. It dynamically extracts exact project dependencies, resolves them to specific versions, and streams deterministic API contracts and interaction rules directly into the LLM's system prompt.

## Core Features
- **Zero-Hallucination API Contracts:** Injects exact function signatures based on the specific version of the library you are using.
- **Architectural Guardrails:** Enforces complex interaction patterns (e.g., "Temporal workflows cannot be executed directly inside FastAPI route handlers").
- **Language Agnostic Architecture:** Built on a provider interface allowing expansion beyond Python to Node, Rust, Go, etc.

## Resolution Architecture

The engine uses a strict **Tiered Fallback Strategy** to guarantee dependency accuracy before building the specification:

1. **Tier 1: Lock Files (Highest Priority)**
   * Parses deterministic manifests (e.g., `poetry.lock`) to extract exact, pinned versions.
2. **Tier 2: Declaration Files**
   * Parses abstract declarations (e.g., `pyproject.toml`, `requirements.txt`).
   * Connects to ecosystem registries (like PyPI) to resolve loose constraints (like `^1.2.0`) to the latest compatible version.
3. **Tier 3: Containerized Introspection (Future)**
   * Sandboxed subprocess execution (`pip freeze`, `npm ls`) for deeply nested or hidden dependencies.

## Component Flow

1. **`TechnologyDetector`**: Scans the repository or user prompt against a curated list of ~180 production-grade technologies to identify the stack.
2. **`DependencyResolver`**: Orchestrates the tiered fallback logic across all available Ecosystem Providers.
3. **`EcosystemProvider`** (e.g., `PythonProvider`): Parses the specific manifest syntax of the language.
4. **`PypiClient`**: Makes async, defensive network requests to fetch current metadata and documentation sources.
5. **`SpecBuilder`**: Assembles the final, non-negotiable System Prompt block, formatting parameters, return types, and deprecation warnings.

## Usage / Integration

Currently, the engine provides internal APIs to assemble the System Prompt constraints. 

```python
# Example Internal Flow (Pseudocode)
from src.service.resolver import DependencyResolver
from src.service.spec_builder import SpecBuilder

# 1. Resolve exact versions used in the project
resolver = DependencyResolver(providers=[PythonProvider(...)])
resolved_deps = await resolver.resolve(Path("./my_project"))

# 2. Fetch the metadata/signatures internally 
# ...

# 3. Build the strict constraints for the LLM
builder = SpecBuilder()
system_instruction = builder.build_system_prompt(api_indexes, patterns)

print(system_instruction) 
# Outputs: 
# ## litellm 1.40.0
# - completion(model: str, messages: list) -> ModelResponse
# ⚠ PATTERN: fastapi + temporalio
# Rule [NO_WORKFLOW_IN_HANDLER]: Workflows must run in workers.
```

## Contributing
When adding a new Ecosystem Provider (e.g., NodeProvider), you must adhere to the asynchronous contract defined in src/providers/base.py. All registry interactions must be defensive and non-blocking.