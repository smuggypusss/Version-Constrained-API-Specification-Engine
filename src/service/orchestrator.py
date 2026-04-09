from __future__ import annotations

import logging
from pathlib import Path

from src.providers.base import ApiIndex, ResolvedDependency, TechnologyPattern

logger = logging.getLogger(__name__)

MAX_RETRY_ATTEMPTS = 3


class Orchestrator:

    async def run(self, prompt: str, repo_path: Path) -> str:
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
        ...

    async def _generation_loop(
        self,
        prompt: str,
        system_prompt: str,
        api_indexes: list[ApiIndex],
        patterns: list[TechnologyPattern],
        dependencies: list[ResolvedDependency],
    ) -> str:
        ...
