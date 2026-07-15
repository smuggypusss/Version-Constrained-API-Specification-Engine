from __future__ import annotations

import logging

from vcase.providers.base import ApiIndex, TechnologyPattern

logger = logging.getLogger(__name__)


class SpecBuilder:

    def build_system_prompt(
        self,
        api_indexes: list[ApiIndex],
        patterns: list[TechnologyPattern],
        user_prompt: str = ""
    ) -> str:
        import re
        # Tokenize user_prompt into keywords
        words = set(re.findall(r'[a-zA-Z_0-9]+', user_prompt.lower())) if user_prompt else set()
        stop_words = {
            "write", "a", "an", "the", "call", "using", "in", "of", "and", "or", 
            "to", "for", "with", "python", "code", "run", "make", "create", "app", 
            "that", "how", "does", "get", "post", "api", "function", "method", 
            "class", "use", "simple", "example", "sample", "test", "write", "generate",
            "code", "program", "script", "file", "build", "implement"
        }
        keywords = words - stop_words

        api_contracts_parts = []
        for index in api_indexes:
            # Filter signatures for this package to avoid hitting context limits
            package = index.package
            filtered = []
            for sig in index.signatures:
                qualified_name_lower = sig.qualified_name.lower()
                parts = qualified_name_lower.split(".")
                simple_name = parts[-1]
                
                # Check relevance
                is_relevant = False
                if keywords:
                    is_relevant = simple_name in keywords or any(kw in qualified_name_lower for kw in keywords)
                
                # Assign priority: 0 for keyword match, 1 for top-level module functions, 2 for nested functions
                if is_relevant:
                    prio = 0
                elif len(parts) <= 2:
                    prio = 1
                else:
                    prio = 2
                filtered.append((sig, prio))
            
            # Sort by priority and limit to 150 signatures per package (to keep overall under context limit)
            filtered.sort(key=lambda x: x[1])
            selected_signatures = [sig for sig, prio in filtered[:150]]
            
            # Format contract with only the selected signatures
            if selected_signatures:
                lines = [f"## {package}@{index.version}"]
                for sig in selected_signatures:
                    params = ",".join(f"{p.name}:{p.type_hint}" for p in sig.parameters)
                    line = f"- {sig.qualified_name}({params}) -> {sig.return_type}"
                    if sig.deprecated:
                        line += f"  - Deprecated: {sig.deprecation_note}"
                    lines.append(line)
                api_contracts_parts.append("\n".join(lines))

        api_contracts = "\n".join(api_contracts_parts) if api_contracts_parts else "No API contracts provided."
        patterns_parts = []
        for pattern in patterns:
            patterns_parts.append(self._format_interaction_pattern(pattern))
        interaction_patterns = "\n".join(patterns_parts) if patterns_parts else "No interaction patterns provided."
        
        PROMPT = f"""
        You are an expert software engineer and an expert in API design and usage.
        Your task is to analyze the user's request and generate code that strictly adheres to the provided API specifications and interaction patterns.
        You must follow these rules:
        1. **Strict Adherence**: You must use the APIs exactly as specified in the API Contracts section.
        2. **Pattern Compliance**: You must follow the Interaction Patterns section. If a pattern is marked as "Incorrect", you must not generate code that matches it.
        3. **No Hallucination**: You must not invent API signatures, parameters, or return types that are not listed in the API Contracts. If an API contract contradicts you training data, your training data is obsolete. Trust only the API Contracts.
        4. **Version Awareness**: The API Contracts are specific to the versions listed. Ensure your code is compatible with these versions.
        ## API Contracts
        {api_contracts}
        ## Interaction Patterns
        {interaction_patterns}
        """
        return PROMPT


    def _format_api_contract(self, index: ApiIndex) -> str:
        package=index.package
        version=index.version
        signatures=index.signatures
        lines=[f"## {package}@{version}"]
        for sig in signatures:
            params=",".join(f"{p.name}:{p.type_hint}" for p in sig.parameters)
            line=f"- {sig.qualified_name}({params}) -> {sig.return_type}"
            if sig.deprecated:
                line += f"  - Deprecated: {sig.deprecation_note}"
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
        

