from __future__ import annotations

import os
import httpx

from vcase.api.pypi_client import PypiClient
from vcase.api.npm_client import NpmClient
from vcase.service.api_index_cache import ApiIndexCache
from vcase.providers.python_provider import PythonProvider
from vcase.providers.node_provider import NodeProvider
from vcase.service.detector import TechnologyDetector
from vcase.service.resolver import DependencyResolver
from vcase.service.retriever import DocumentationRetriever
from vcase.service.spec_builder import SpecBuilder
from vcase.service.api_validator import ApiValidator
from vcase.service.architecture_validator import ArchitectureValidator
from vcase.service.llm_validator import LlmValidator
from vcase.service.orchestrator import Orchestrator


def create_orchestrator(
    http_client: httpx.AsyncClient,
    model_name: str | None = None,
    api_key: str | None = None,
    provider: str | None = None,
) -> Orchestrator:
    """Helper factory function to construct a fully configured Orchestrator pipeline."""
    pypi_client = PypiClient(http_client)
    npm_client = NpmClient(http_client)
    cache = ApiIndexCache(http_client)

    python_prov = PythonProvider(pypi_client, cache)
    node_prov = NodeProvider(npm_client)

    detector = TechnologyDetector([python_prov, node_prov])
    resolver = DependencyResolver([python_prov, node_prov])
    retriever = DocumentationRetriever([python_prov, node_prov])
    
    spec_builder = SpecBuilder()
    api_validator = ApiValidator()
    arch_validator = ArchitectureValidator()
    
    llm_validator = LlmValidator(
        model_name=model_name,
        api_key=api_key,
        provider=provider
    )

    return Orchestrator(
        detector=detector,
        resolver=resolver,
        retriever=retriever,
        spec_builder=spec_builder,
        api_validator=api_validator,
        architecture_validator=arch_validator,
        llm_validator=llm_validator,
        model_name=model_name,
        api_key=api_key,
        provider=provider
    )
