from __future__ import annotations

import logging

from src.providers.base import ApiIndex, TechnologyPattern

logger = logging.getLogger(__name__)


class SpecBuilder:

    def build_system_prompt(
        self,
        api_indexes: list[ApiIndex],
        patterns: list[TechnologyPattern],
    ) -> str:
        """
        Construct an enforcement system prompt from API contracts and interaction patterns.
        The prompt must frame constraints as hard rules, not suggestions.
        """
        ...

    def _format_api_contract(self, index: ApiIndex) -> str:
        package=index.package
        version=index.version
        signatures=index.signatures
        lines=[f"## {package}@{version}"]
        for sig in signatures:
            params=",".join(f"{p.name}:{p.type_hint}" for p in sig.parameters)
            line=f"- {sig.qualified_name}({params}) -> {sig.return_type}"
            if sig.deprecated:
                line.append(f"  - Deprecated: {sig.deprecation_note}")
            lines.append(line)

        return "\n".join(lines)

        

    def _format_interaction_pattern(self, pattern: TechnologyPattern) -> str:
        name=pattern.technologies
        description=pattern.description
        correct_pattern=pattern.correct_pattern
        incorrect_pattern=pattern.incorrect_pattern
        rule_name=pattern.constraint.rule_name
        rule_desc=pattern.constraint.description
        disallowed_in = pattern.constraint.disallowed_in
        allowed_in    = pattern.constraint.allowed_in
        technologies_str = " + ".join(name)
        disallowed_str   = ", ".join(disallowed_in)
        allowed_str      = ", ".join(allowed_in)
        return (
            f"Pattern: {technologies_str}\n"
            f"Description: {description}\n"
            f"Correct Pattern: {correct_pattern}\n"
            f"Incorrect Pattern: {incorrect_pattern}\n"
            f"Disallowed In: {disallowed_str}\n"
            f"Allowed In: {allowed_str}\n"
            f"Rule Name: [{rule_name}]: {rule_desc}\n"
        )
        

