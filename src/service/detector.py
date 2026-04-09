from __future__ import annotations

import logging
from pathlib import Path

from src.providers.base import Ecosystem, EcosystemProvider, ResolvedDependency

logger = logging.getLogger(__name__)

KNOWN_TECHNOLOGIES: frozenset[str] = frozenset({
    # ── Web Frameworks ──────────────────────────────────────────────────────
    "fastapi", "flask", "django", "starlette", "aiohttp", "tornado",
    "sanic", "quart", "gunicorn", "uvicorn", "hypercorn",
    "flask-restful", "flask-restx", "djangorestframework",
    "flask-sqlalchemy", "flask-login", "flask-jwt-extended",
    "flask-cors", "flask-migrate", "flask-caching", "flask-session",
    "flask-wtf", "flask-limiter", "flask-socketio",

    # ── ASGI / Server ───────────────────────────────────────────────────────
    "uvloop", "httptools", "websockets", "sse-starlette",

    # ── HTTP Clients ────────────────────────────────────────────────────────
    "httpx", "requests", "aiohttp",

    # ── Data Validation / Serialisation ────────────────────────────────────
    "pydantic", "pydantic-settings", "marshmallow", "attrs",

    # ── Databases / ORMs ────────────────────────────────────────────────────
    "sqlalchemy", "alembic", "sqlmodel",
    "asyncpg", "psycopg2", "psycopg", "pymysql", "aiomysql",
    "pymongo", "motor", "mongoengine", "beanie",
    "redis", "aioredis",
    "elasticsearch", "opensearch-py",
    "pymilvus", "weaviate-client", "qdrant-client", "pinecone",
    "chromadb", "pgvector", "lancedb",
    "duckdb", "sqlite-vec",
    "firebase-admin", "supabase",
    "neo4j", "cassandra-driver",

    # ── Task Queues / Workflow Engines ──────────────────────────────────────
    "celery", "kombu", "billiard", "redis",
    "temporalio",   # Temporal SDK for Python
    "prefect", "dagster", "apache-airflow",
    "ray", "dask", "rq", "huey",
    "apscheduler", "arq",

    # ── AI / LLM / ML ───────────────────────────────────────────────────────
    "openai", "anthropic", "groq", "cohere", "mistralai",
    "google-generativeai", "google-genai",
    "litellm",
    "langchain", "langchain-core", "langchain-openai",
    "langchain-anthropic", "langchain-google-genai",
    "langchain-community", "langchain-text-splitters",
    "langgraph", "langgraph-prebuilt",
    "langsmith",
    "langfuse",
    "llama-index", "llama-index-core",
    "huggingface-hub", "transformers", "sentence-transformers",
    "accelerate", "diffusers", "peft", "trl",
    "torch", "torchvision", "torchaudio",
    "tensorflow", "keras", "jax",
    "scikit-learn", "xgboost", "lightgbm", "catboost",
    "mlflow", "wandb", "optuna",
    "pydantic-ai", "openai-agents", "crewai",
    "instructor", "dspy", "semantic-kernel",
    "ollama", "vllm", "sglang",
    "faiss-cpu", "onnxruntime",

    # ── Observability / Monitoring ──────────────────────────────────────────
    "opentelemetry-api", "opentelemetry-sdk",
    "sentry-sdk", "datadog", "prometheus-client",
    "logfire", "loguru", "structlog",
    "posthog",

    # ── Messaging / Streaming ────────────────────────────────────────────────
    "kafka-python", "confluent-kafka", "aiokafka",
    "pika",  # RabbitMQ
    "nats-py",

    # ── Cloud SDKs ───────────────────────────────────────────────────────────
    "boto3", "botocore",                 # AWS
    "google-cloud-storage",             # GCP
    "azure-core", "azure-identity",     # Azure
    "kubernetes",

    # ── Auth / Security ──────────────────────────────────────────────────────
    "pyjwt", "python-jose", "authlib", "passlib",
    "cryptography", "bcrypt",

    # ── Testing ──────────────────────────────────────────────────────────────
    "pytest", "pytest-asyncio", "pytest-mock", "hypothesis",

    # ── Data / Science ───────────────────────────────────────────────────────
    "numpy", "pandas", "scipy", "matplotlib", "seaborn", "plotly",
    "pillow", "opencv-python", "scikit-image",

    # ── CLI ──────────────────────────────────────────────────────────────────
    "click", "typer", "rich", "textual",

    # ── Async Utilities ──────────────────────────────────────────────────────
    "anyio", "trio", "asyncio",

    # ── Document / File Processing ───────────────────────────────────────────
    "pypdf", "pdfminer-six", "python-docx", "openpyxl",
    "beautifulsoup4", "lxml", "scrapy", "playwright", "selenium",

    # ── GraphQL ──────────────────────────────────────────────────────────────
    "graphql-core", "strawberry-graphql", "ariadne", "graphene",

    # ── gRPC ─────────────────────────────────────────────────────────────────
    "grpcio",

    # ── Configuration ────────────────────────────────────────────────────────
    "python-dotenv", "dynaconf", "pydantic-settings",
})

class TechnologyDetector:

    def __init__(self, providers: list[EcosystemProvider]) -> None:
        self._providers=providers

    def detect_ecosystems(self, repo_path: Path) -> list[EcosystemProvider]:
        """Return all providers that apply to the given repository."""
        detected_providers=[]
        for provider in self._providers:
            if provider.detect(repo_path):
                detected_providers.append(provider)
        return detected_providers

    def detect_technologies_in_prompt(self, prompt: str) -> list[str]:
        """Extract technology names referenced in the user prompt."""
        prompt_lower = prompt.lower()
        return [tech for tech in KNOWN_TECHNOLOGIES if tech in prompt_lower]
