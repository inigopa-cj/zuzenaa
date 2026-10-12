"""Embeddings del tutor, 100 % locales (nada sale a internet).

``Embedder`` es la interfaz: hoy un vectorizador por *hashing* (sin modelo, sin
descargas, determinista) y mañana un modelo local (p. ej. Ollama) detrás de la
misma interfaz. El hashing captura vocabulario compartido (palabras y pares de
palabras, sin tildes), suficiente para recuperar apuntes y feedback relacionados con
una pregunta en un corpus de clase.
"""

from __future__ import annotations

import hashlib
import math
import re
import unicodedata
from itertools import pairwise
from typing import Protocol

DIMENSIONS = 512

# Palabras vacías (castellano + euskera básico) que no aportan al significado.
_STOPWORD_TEXT = """
a al algo como con cual cuando de del desde donde el ella en entre es esa ese eso
esta este esto fue ha hay la las le lo los me mi mas muy no o para pero por que se
si sin sobre su sus te tu un una uno unos y ya yo
eta da ez bat du dut zer nola edo baina ere
"""
_STOPWORDS = frozenset(_STOPWORD_TEXT.split())


class Embedder(Protocol):
    name: str

    def embed(self, text: str) -> list[float]: ...


def tokens(text: str) -> list[str]:
    plain = unicodedata.normalize("NFKD", text.lower()).encode("ascii", "ignore").decode()
    words: list[str] = []
    for word in re.findall(r"[a-z0-9_]{2,}", plain):
        words.append(word)
        if "_" in word:
            words.extend(part for part in word.split("_") if len(part) >= 2)
    return [w for w in words if w not in _STOPWORDS]


def _bucket(feature: str) -> tuple[int, float]:
    digest = hashlib.blake2b(feature.encode(), digest_size=8).digest()
    value = int.from_bytes(digest, "big")
    return value % DIMENSIONS, (1.0 if value >> 63 else -1.0)


class HashingEmbedder:
    """Unigramas + bigramas con *feature hashing* firmado y tf sublineal (L2)."""

    name = "hashing"

    def embed(self, text: str) -> list[float]:
        words = tokens(text)
        features = words + [f"{a} {b}" for a, b in pairwise(words)]
        counts: dict[str, int] = {}
        for feature in features:
            counts[feature] = counts.get(feature, 0) + 1
        vector = [0.0] * DIMENSIONS
        for feature, count in counts.items():
            index, sign = _bucket(feature)
            vector[index] += sign * (1.0 + math.log(count))
        norm = math.sqrt(sum(v * v for v in vector))
        return [v / norm for v in vector] if norm else vector


def cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=False))  # ambos normalizados (L2)


def get_embedder() -> Embedder:
    return HashingEmbedder()


__all__ = ["DIMENSIONS", "Embedder", "HashingEmbedder", "cosine", "get_embedder", "tokens"]
