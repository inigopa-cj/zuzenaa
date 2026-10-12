"""Quita los datos personales del contexto antes de que llegue al agente/LLM.

Regla dura: la identidad del alumnado (login de GitHub, nombre y apellidos) **nunca**
sale hacia un proveedor LLM. Se sustituye por su seudónimo en todo el contexto
(código, diff, rutas, feedback anterior...) y después se comprueba que no quede
ninguna; si quedara, el análisis se bloquea en vez de enviarse.
"""

from __future__ import annotations

import re
from collections.abc import Iterable


def _pattern(terms: Iterable[str]) -> re.Pattern[str] | None:
    words = sorted({t for t in terms if t}, key=len, reverse=True)
    if not words:
        return None
    # Límites de palabra «a mano»: el login puede llevar guiones y \b no los cubre.
    alternation = "|".join(re.escape(w) for w in words)
    return re.compile(rf"(?<![A-Za-z0-9_])(?:{alternation})(?![A-Za-z0-9_])", re.IGNORECASE)


def scrub(value: object, terms: Iterable[str], alias: str) -> object:
    """Copia de ``value`` (str/list/dict anidados) con cada término → ``alias``."""
    pattern = _pattern(terms)
    if pattern is None:
        return value

    def walk(item: object) -> object:
        if isinstance(item, str):
            return pattern.sub(alias, item)
        if isinstance(item, list):
            return [walk(x) for x in item]
        if isinstance(item, tuple):
            return tuple(walk(x) for x in item)
        if isinstance(item, dict):
            return {walk(k) if isinstance(k, str) else k: walk(v) for k, v in item.items()}
        return item

    return walk(value)


def leaks(value: object, terms: Iterable[str]) -> list[str]:
    """Términos personales que siguen apareciendo en ``value`` (debería ser vacío)."""
    pattern = _pattern(terms)
    if pattern is None:
        return []
    found: set[str] = set()

    def walk(item: object) -> None:
        if isinstance(item, str):
            found.update(m.group(0).lower() for m in pattern.finditer(item))
        elif isinstance(item, (list, tuple)):
            for x in item:
                walk(x)
        elif isinstance(item, dict):
            for k, v in item.items():
                walk(k)
                walk(v)

    walk(value)
    return sorted(found)


__all__ = ["leaks", "scrub"]
