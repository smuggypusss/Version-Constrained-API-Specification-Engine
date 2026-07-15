from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CallIR:
    """
    Normalized representation of a single function/method call.
    Produced by language adapters. Consumed by the rules engine.

    Example input code:
        litellm.completion(model="gpt-4o", messages=[...])

    Example output:
        CallIR(receiver="litellm", method="completion", kwargs=["model", "messages"])
    """
    receiver: str | None       # The object being called on. e.g. "litellm"
    method: str                # The method or function name. e.g. "completion"
    args_count: int           # Positional argument names (best-effort)
    kwargs: list[str]          # Keyword argument names. e.g. ["model", "messages"]
    context: list[str]         # Enclosing decorator context. e.g. ["app.post"]


@dataclass
class CodeFileIR:
    """
    Normalized representation of an entire source file.
    This is the language-independent structure that the rules engine operates on.

    Fields:
        imports  — list of top-level module/package imports.
        calls    — list of all function/method call sites found in this file.
    """
    filepath: str
    imports: list[str] = field(default_factory=list)
    calls: list[CallIR] = field(default_factory=list)
    aliases: dict[str, str] = field(default_factory=dict)
