"""Proveedor de respuestas del tutor.

``MockTutor`` es la respuesta sin modelo (modo básico): compone la respuesta con los
fragmentos recuperados y cita cada uno, sin inventar nada. Se usa cuando no hay
proveedor configurado o falla; el agente con modelo real vive en ``tutor/agent.py``.
"""

from __future__ import annotations

import re
from typing import Protocol

from zuzenaa.agent import guardrails
from zuzenaa.tutor.embeddings import tokens
from zuzenaa.tutor.store import Passage

NO_CONTEXT = (
    "No encuentro nada sobre esto en el material de tu clase, en tu feedback ni en la guía "
    "de ZuzenAA. Reformula la duda con otras palabras o pregúntasela a tu profesorado."
)

_SENTENCE = re.compile(r"(?<=[.!?])\s+")
# Peticiones de que el tutor haga el trabajo: se responde orientando, nunca con código.
_WANTS_SOLUTION = re.compile(
    r"\b(c[oó]digo|soluci[oó]n|resu[eé]lve|hazme|haz el|escr[ií]beme|copiar|p[aá]same)\b",
    re.IGNORECASE,
)
NO_SOLUTIONS = (
    "No escribo código ni doy soluciones, pero puedo orientarte con lo que tienes en tu "
    "material."
)


class TutorProvider(Protocol):
    name: str

    async def answer(self, *, question: str, passages: list[Passage]) -> str:
        """Respuesta en texto plano que cita los fragmentos como [1], [2]..."""
        ...


def topic_only(question: str) -> str:
    """La pregunta sin las palabras de petición de solución, para recuperar por tema."""
    return _WANTS_SOLUTION.sub(" ", question)


def is_safe(text: str) -> bool:
    """Mismas reglas que el agente: sin código ni soluciones."""
    return guardrails.text_violation(text) is None


def _summary(text: str, question: str, max_sentences: int = 2) -> str:
    """Las frases más relacionadas con la pregunta, en su orden original."""
    sentences = [s.strip() for s in _SENTENCE.split(text.replace("\n", " ")) if s.strip()]
    safe = [s for s in sentences if is_safe(s)]
    wanted = set(tokens(question))
    ranked = sorted(range(len(safe)), key=lambda i: (-len(wanted & set(tokens(safe[i]))), i))
    return " ".join(safe[i] for i in sorted(ranked[:max_sentences]))


class MockTutor:
    name = "mock"

    async def answer(self, *, question: str, passages: list[Passage]) -> str:
        wants_solution = bool(_WANTS_SOLUTION.search(question))
        nothing = f"{NO_SOLUTIONS} {NO_CONTEXT}" if wants_solution else NO_CONTEXT
        if not passages:
            return nothing
        intro = "Esto es lo que encuentro para tu duda:"
        if wants_solution:
            intro = f"{NO_SOLUTIONS} {intro}"
        parts = [intro]
        for number, passage in enumerate(passages[:3], start=1):
            where = passage.title + (f" / {passage.heading}" if passage.heading else "")
            summary = _summary(passage.text, question)
            if summary:
                parts.append(f"[{number}] Según «{where}»: {summary}")
        if len(parts) == 1:
            return nothing
        if any(p.source in {"feedback", "correccion"} for p in passages[:3]):
            parts.append(
                "Relaciónalo con la pista de tu feedback: prueba ese caso en tu ordenador "
                "antes de volver a subir."
            )
        else:
            parts.append("Léelo con calma y prueba un ejemplo pequeño antes de seguir.")
        return "\n\n".join(parts)


def build_tutor(provider: str) -> TutorProvider:
    if provider in {"mock", "none", ""}:
        return MockTutor()
    raise ValueError(f"proveedor del tutor no soportado todavía: {provider!r} (solo 'mock')")


def get_tutor() -> TutorProvider:
    from zuzenaa.config import settings

    return build_tutor(settings.llm_provider)


__all__ = [
    "NO_CONTEXT",
    "MockTutor",
    "TutorProvider",
    "build_tutor",
    "get_tutor",
    "is_safe",
    "topic_only",
]
