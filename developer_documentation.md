# Version-Constrained API Specification Engine — Developer Guide

This document provides a detailed overview of the system architecture, component modules, and design philosophy of the **Version-Constrained API Specification Engine**. This guide is written for engineers looking to contribute to, extend, or integrate with the system.

---

## 1. System Philosophy

Coding LLMs suffer from a **knowledge cutoff problem** and **prior training bias**. When frameworks release updates, models rely on outdated training parameters or hallucinate API signatures. Conventional RAG solutions inject verbose tutorials or outdated logs, leading to **context dilution** and **obedience failures**.

Our engine operates as a **deterministic compiler-like toolchain** rather than an agentic loop. It enforces exact versioned contracts in a **five-layer defense system**:

```
[User Prompt + Codebase Path]
             │
             ▼
    Technology Detection
             │
             ▼
    Dependency Resolution (Tiered Fallback)
             │
             ▼
    API Spec / Contract Retrieval (AST Ingestion)
             │
             ▼
    Interaction Constraint Application
             │
             ▼
    LLM Code Generation (System Spec Injection)
             │
             ▼
    Validation (AST checks + Rules + LLM judge)
             │
             ▼
[Validated Code / Trace Log]
```

---

## 2. Directory and Component Structure

```
├── pyproject.toml              # Packaging build configuration metadata
├── requirements.txt            # Dependency list
├── tests/                      # Python pytest suite
└── vcase/                      # Root package namespace
    ├── __init__.py             # Public library exports & factory helper
    ├── cli.py                  # CLI commands handler (serve, run)
    ├── main.py                 # FastAPI application definition
    ├── api/                    # Ecosystem Registry clients (PyPI, npm)
    ├── providers/              # Ecosystem providers (Python, Node)
    ├── routers/                # FastAPI routing layers (health, proxy)
    ├── service/                # Core engine services (resolver, orchestrator)
    └── validator/              # AST rules engine, adapters, and IR
```

---

## 3. Component Details & Data Contracts

### 3.1 Shared Data Models (`vcase/providers/base.py`)
All components communicate using standard, frozen dataclasses:

- **`RawDependency`**: Extracted package name and version range constraint (e.g. `fastapi>=0.100.0`).
- **`ResolvedDependency`**: Absolute pinned version (e.g. `fastapi` at `0.115.0`) along with its `resolution_tier`.
- **`ApiSignature`**: Pinned signature containing name, type-hinted parameter list, return type, and deprecation details.
- **`ApiIndex`**: Collection of signatures for a given package and version.
- **`InteractionConstraint`**: Declares forbidden decorator/call contexts for a tech combination (e.g. "no SQL database operations inside async FastAPI route handlers").

### 3.2 Ingestion & AST Parsing (`vcase/service/ast_parser.py`)
The system avoids third-party scraper unreliability by downloading code source packages directly from official registries (e.g. PyPI wheels) and parsing them with Python's built-in `ast` module.
- Generates an `ApiIndex` containing public functions, arguments (names, types, defaults), and return annotations.
- Converts complex AST annotation structures into normalized strings (e.g., `tuple[str, ...]` or `int | None`).

### 3.3 Cache Layer (`vcase/service/api_index_cache.py`)
- **Memory Cache**: Process-lifetime index storage.
- **Disk Cache**: JSON serialized indexes stored under `~/.cache/vcase/{package}/{version}/api_index.json`.

---

## 4. The Five Layers of Defense

1. **Exact Version Pinning**: Resolves loose constraints using lock files (`poetry.lock`, `package-lock.json`) before falling back to declarations and registries.
2. **Defensive API Specifications**: Injects typed signatures into the system prompt, instructing the LLM to treat them as absolute, overriding compile-time rules.
3. **Multi-technology Constraints**: Injects canonical patterns and composition rules derived from official integration specs.
4. **Layer 1 Validator (Static AST)**: Runs a parsing pass using `PythonAdapter` over generated outputs to ensure all called APIs exist and parameters conform to the contract.
5. **Layer 2 Validator (Architectural Rules)**: Checks that calls aren't executing inside disallowed contexts (e.g., executing Temporal workflows directly inside endpoints).

---

## 5. Extending the Engine (Developer Checklist)

To add support for a new programming ecosystem (e.g. Rust or Go):
1. **Extend `EcosystemProvider`** (`vcase/providers/base.py`): Implement file detector, manifest parser, version resolver, and registry client.
2. **Implement Registry API Client** (`vcase/api/`): Create a client query wrapper for Crates.io, Maven Central, etc.
3. **Register Provider** inside `vcase/__init__.py` (the `create_orchestrator` factory) to expose it to the `DependencyResolver`.

---

## 6. Pip Package & CLI Usage

Once packaged and installed, VCASE can be invoked as a global CLI tool or imported directly as a programmatic library.

### 6.1 Installation
Install locally or in editable development mode from the project root:
```bash
pip install .
# or for editable/development mode:
pip install -e .
```

### 6.2 Command-Line Interface (CLI)
VCASE registers a global command `vcase` (linked to `vcase.cli:main`).

#### Start the API server:
```bash
vcase serve --port 8000
```
Starts the FastAPI backend proxy server running via Uvicorn.

#### Direct CLI generation & validation:
```bash
vcase run --prompt "Write a litellm completion call" \
          --repo-path "./path/to/repo" \
          --provider "groq" \
          --model "llama3-8b-8192" \
          --api-key "gsk_xxxx..."
```
Arguments:
- `--prompt`: User prompt/instruction (Required).
- `--repo-path`: Path to local repository to resolve dependencies (Required).
- `--provider`: LLM provider to use (`openai`, `gemini`, `openrouter`, or `groq`) (Optional).
- `--model`: Custom LLM model name (Optional).
- `--api-key`: Custom API key to authenticate with the chosen provider (Optional).

### 6.3 Programmatic Import
Import `vcase` modules and configure them with custom models and providers dynamically:
```python
import httpx
import asyncio
from vcase import create_orchestrator

async def run():
    async with httpx.AsyncClient() as client:
        # Create an orchestrator with custom configuration
        orchestrator = create_orchestrator(
            http_client=client,
            model_name="llama3-8b-8192",
            provider="groq",
            api_key="gsk_xxxx..."
        )
        # Execute query
        code = await orchestrator.run("Write a litellm completion call", "./tests")
        print(code)

asyncio.run(run())
```

