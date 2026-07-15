from __future__ import annotations

import logging
import re

from vcase.providers.base import ApiIndex, ApiSignature, ApiParameter

logger = logging.getLogger(__name__)


class ContractExtractor:

    def extract(self, raw_content: str, package: str, version: str) -> ApiIndex:
        """
        Parse raw documentation markdown/text and extract structured API signatures.
        Extracts lines matching: `- function_name(arg1: type, ...) -> return_type`
        """
        signatures = []
        lines = raw_content.splitlines()
        for line in lines:
            line = line.strip()
            # Match pattern: - qualified_name(params) -> return_type
            match = re.match(r"^-\s+([\w\.]+)\((.*?)\)\s*->\s*([\w\.\d\[\]\| ]+)", line)
            if match:
                qualified_name = match.group(1)
                params_str = match.group(2)
                return_type = match.group(3).strip()

                parameters = []
                if params_str.strip():
                    # Split parameters by comma
                    parts = params_str.split(",")
                    for part in parts:
                        part = part.strip()
                        if ":" in part:
                            p_name, p_type = part.split(":", 1)
                            parameters.append(ApiParameter(
                                name=p_name.strip(),
                                type_hint=p_type.strip(),
                                required=True,
                                description=""
                            ))
                        else:
                            parameters.append(ApiParameter(
                                name=part.strip(),
                                type_hint="Any",
                                required=True,
                                description=""
                            ))

                signatures.append(ApiSignature(
                    qualified_name=qualified_name,
                    parameters=tuple(parameters),
                    return_type=return_type,
                    available_since="",
                    deprecated=False
                ))

        return ApiIndex(
            package=package,
            version=version,
            signatures=tuple(signatures)
        )

    def _parse_function_signature(self, raw: str) -> ApiSignature | None:
        # Internal parser helper
        return None
