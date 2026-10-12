"""Trocea documentos (Markdown/texto) en fragmentos para el índice del tutor.

Respeta los encabezados (cada fragmento recuerda su sección, que se usa en las citas)
y agrupa párrafos hasta ``max_chars``. Los bloques de código se quitan: el tutor
orienta, no entrega código.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

MAX_CHARS = 900

_HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
_FENCE = re.compile(r"```.*?```", re.DOTALL)


@dataclass
class Chunk:
    heading: str | None
    text: str


def split(text: str, *, max_chars: int = MAX_CHARS) -> list[Chunk]:
    clean = _FENCE.sub("", text.replace("\r\n", "\n"))
    chunks: list[Chunk] = []
    heading: str | None = None
    buffer: list[str] = []

    def flush() -> None:
        body = "\n\n".join(p for p in buffer if p).strip()
        if body:
            chunks.append(Chunk(heading, body))
        buffer.clear()

    paragraph: list[str] = []
    for line in [*clean.split("\n"), ""]:
        match = _HEADING.match(line.strip())
        if match:
            buffer.append(" ".join(paragraph).strip())
            paragraph = []
            flush()
            heading = match.group(2).strip()[:200]
            continue
        if line.strip():
            paragraph.append(line.strip())
            continue
        text = " ".join(paragraph).strip()
        paragraph = []
        if not text:
            continue
        if sum(len(p) for p in buffer) + len(text) > max_chars:
            flush()
        while len(text) > max_chars:  # párrafo enorme: cortar por frases
            cut = text.rfind(". ", 0, max_chars)
            cut = cut + 1 if cut > 0 else max_chars
            buffer.append(text[:cut].strip())
            flush()
            text = text[cut:].strip()
        buffer.append(text)
    flush()
    return chunks


__all__ = ["MAX_CHARS", "Chunk", "split"]
