"""Pedagogical guardrails: block feedback that leaks code or the solution.

Defence in depth, in order:
1. Schema validation (the provider's output must parse as AgentFeedback).
2. Forbidden-content rules over the rendered fields.
3. Optional judge (a second LLM call) — not wired yet.

Anything that fails is never posted; the caller records the violation.
"""

from __future__ import annotations

import re

from zuzenaa.agent.schema import AgentFeedback

# Signals that the text is answering instead of guiding.
_CODE_FENCE = re.compile(r"```")
_LINE_OF_CODE = re.compile(r"^\s*(def |class |import |from |return |print\()", re.MULTILINE)
_SOLUTION_WORDS = re.compile(
    r"\b(la soluci[óo]n es|copia|pega este c[óo]digo|aqu[íi] tienes el c[óo]digo)\b",
    re.IGNORECASE,
)

_MAX_FIELD_CHARS = 1200


class GuardrailViolation(RuntimeError):
    """Raised when feedback must not be published."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def _iter_text(feedback: AgentFeedback) -> list[tuple[str, str]]:
    fields = [
        ("funcionalidad", feedback.funcionalidad),
        ("calidad", feedback.calidad),
        ("diseno", feedback.diseno),
        ("pista", feedback.pista.text),
    ]
    if feedback.teoria:
        fields.append(("teoria", feedback.teoria))
    return fields


def enforce(feedback: AgentFeedback) -> None:
    """Raise GuardrailViolation if the feedback breaks the rules."""
    for field, text in _iter_text(feedback):
        if len(text) > _MAX_FIELD_CHARS:
            raise GuardrailViolation(f"campo '{field}' demasiado largo")
        if _CODE_FENCE.search(text):
            raise GuardrailViolation(f"campo '{field}' contiene un bloque de código")
        if _LINE_OF_CODE.search(text):
            raise GuardrailViolation(f"campo '{field}' parece contener código")
        if _SOLUTION_WORDS.search(text):
            raise GuardrailViolation(f"campo '{field}' entrega la solución")
