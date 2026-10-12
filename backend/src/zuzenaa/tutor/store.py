"""Índice del tutor en la propia BD (portable Postgres/SQLite).

Los embeddings se guardan como JSON y la similitud se calcula en el backend: basta
para el corpus de una clase. Si crece, el paso natural es ``pgvector`` en la misma
Postgres sin cambiar la interfaz (``ingest`` / ``search``).

Ámbito de búsqueda: el material de **esa** clase + la documentación de ZuzenAA
(común). Nunca se mezcla material de otras clases.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import and_, delete, or_, select

from zuzenaa.db.models import TutorChunk, TutorDocument
from zuzenaa.db.session import SessionLocal
from zuzenaa.tutor import chunking
from zuzenaa.tutor.embeddings import cosine, get_embedder, tokens
from zuzenaa.util import now_epoch

BUILTIN_DIR = Path(__file__).parent / "corpus"


@dataclass
class Passage:
    source: str  # material | zuzenaa | feedback
    title: str
    heading: str | None
    text: str
    score: float
    ref: str  # identificador estable para citar (p. ej. "doc-3#2")


async def ingest(
    *,
    title: str,
    text: str,
    source: str,
    org: str | None = None,
    classroom: str | None = None,
    filename: str | None = None,
    uploaded_by: str | None = None,
) -> TutorDocument:
    embedder = get_embedder()
    chunks = chunking.split(text)
    digest = hashlib.sha256(text.encode()).hexdigest()
    async with SessionLocal() as session:
        document = TutorDocument(
            org=org,
            classroom=classroom,
            source=source,
            title=title[:200],
            filename=filename,
            content_hash=digest,
            uploaded_by=uploaded_by,
            chunk_count=len(chunks),
            created_at=now_epoch(),
        )
        session.add(document)
        await session.flush()
        for position, chunk in enumerate(chunks):
            session.add(
                TutorChunk(
                    document_id=document.id,
                    position=position,
                    heading=chunk.heading,
                    text=chunk.text,
                    embedding=json.dumps(
                        [round(v, 5) for v in embedder.embed(_indexable(title, chunk))]
                    ),
                )
            )
        await session.commit()
        await session.refresh(document)
        return document


def _indexable(title: str, chunk: chunking.Chunk) -> str:
    return " ".join(part for part in (title, chunk.heading, chunk.text) if part)


async def documents(org: str, classroom: str) -> list[TutorDocument]:
    async with SessionLocal() as session:
        stmt = (
            select(TutorDocument)
            .where(TutorDocument.org == org, TutorDocument.classroom == classroom)
            .order_by(TutorDocument.created_at.desc())
        )
        return list((await session.execute(stmt)).scalars().all())


async def remove(org: str, classroom: str, document_id: int) -> bool:
    async with SessionLocal() as session:
        document = await session.get(TutorDocument, document_id)
        if document is None or (document.org, document.classroom) != (org, classroom):
            return False
        await session.execute(delete(TutorChunk).where(TutorChunk.document_id == document_id))
        await session.delete(document)
        await session.commit()
        return True


async def search(org: str, classroom: str, query: str, *, k: int = 4) -> list[Passage]:
    """Top-k del material de la clase + documentación de ZuzenAA."""
    embedder = get_embedder()
    vector = embedder.embed(query)
    query_words = set(tokens(query))
    scope = or_(
        and_(TutorDocument.org == org, TutorDocument.classroom == classroom),
        TutorDocument.source == "zuzenaa",
    )
    async with SessionLocal() as session:
        rows = (
            await session.execute(
                select(TutorChunk, TutorDocument)
                .join(TutorDocument, TutorChunk.document_id == TutorDocument.id)
                .where(scope)
            )
        ).all()
    scored: list[Passage] = []
    for chunk, document in rows:
        score = cosine(vector, json.loads(chunk.embedding))
        # Reordenación ligera: premia el vocabulario exacto de la pregunta.
        overlap = len(query_words & set(tokens(f"{chunk.heading or ''} {chunk.text}")))
        if not overlap:
            continue  # sin ninguna palabra en común, la similitud es ruido del hashing
        score += 0.05 * overlap
        scored.append(
            Passage(
                source=document.source,
                title=document.title,
                heading=chunk.heading,
                text=chunk.text,
                score=score,
                ref=f"doc-{document.id}#{chunk.position}",
            )
        )
    scored.sort(key=lambda p: p.score, reverse=True)
    return [p for p in scored[:k] if p.score > 0.08]


async def ensure_builtin() -> int:
    """Indexa (o reindexa si cambió) la documentación de ZuzenAA. Idempotente."""
    indexed = 0
    for path in sorted(BUILTIN_DIR.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        digest = hashlib.sha256(text.encode()).hexdigest()
        async with SessionLocal() as session:
            existing = (
                await session.execute(
                    select(TutorDocument).where(
                        TutorDocument.source == "zuzenaa", TutorDocument.filename == path.name
                    )
                )
            ).scalars().all()
            if any(doc.content_hash == digest for doc in existing):
                continue
            for doc in existing:
                await session.execute(delete(TutorChunk).where(TutorChunk.document_id == doc.id))
                await session.delete(doc)
            await session.commit()
        title = text.splitlines()[0].lstrip("# ").strip() if text else path.stem
        await ingest(title=title, text=text, source="zuzenaa", filename=path.name)
        indexed += 1
    return indexed


__all__ = ["Passage", "documents", "ensure_builtin", "ingest", "remove", "search"]
