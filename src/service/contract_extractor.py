from __future__ import annotations

import logging

from src.providers.base import ApiIndex, ApiSignature

logger = logging.getLogger(__name__)


class ContractExtractor:

    def extract(self, raw_content: str, package: str, version: str) -> ApiIndex:
        """
        Parse raw documentation HTML or markdown and extract structured API signatures.
        Never returns prose. Output must be typed and minimal.
        """
        ...

    def _parse_function_signature(self, raw: str) -> ApiSignature | None:
        ...
