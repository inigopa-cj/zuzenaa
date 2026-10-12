"""Responde una duda del alumnado: recuperación (RAG) + privacidad + guardarraíles.

1. La pregunta se limpia de datos personales (login/nombre → seudónimo).
2. Recuperación: material de **esa** clase + guía de ZuzenAA (``store.search``) y el
   **feedback del propio alumno** en esa clase, que se recupera en el momento y nunca
   incluye el de otros.
3. Todo el contexto se limpia y se verifica que no queden datos personales; si
   quedaran, no se envía al proveedor.
4. La respuesta pasa los mismos guardarraíles que el agente (sin código ni soluciones)
   y siempre lleva sus citas.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from sqlalchemy import func, select

from zuzenaa.db.models import Analysis, Repository
from zuzenaa.db.session import SessionLocal
from zuzenaa.privacy import pseudonyms
from zuzenaa.privacy.scrub import leaks, scrub
from zuzenaa.tutor import store
from zuzenaa.tutor.embeddings import cosine, get_embedder, tokens
from zuzenaa.tutor.provider import get_tutor, is_safe, topic_only
from zuzenaa.tutor.store import Passage

MAX_QUESTION_CHARS = 1000
BLOCKED = (
    "No puedo responder a eso con seguridad. Recuerda que el tutor orienta: no escribe código "
    "ni da soluciones. Prueba a preguntar por el concepto o por la pista de tu feedback."
)


@dataclass
class Citation:
    number: int
    source: str  # material | zuzenaa | feedback
    title: str
    heading: str | None
    snippet: str
    ref: str


@dataclass
class TutorReply:
    answer: str
    citations: list[Citation]
    blocked: bool
    provider: str


@dataclass
class Correction:
    """La corrección (análisis de un commit) desde la que el alumno abre el tutor."""

    analysis_id: int
    assignment: str
    owner: str  # login: solo dentro del backend
    commit_sha: str
    passage: Passage


async def load_correction(org: str, classroom: str, analysis_id: int) -> Correction | None:
    """La corrección ``analysis_id`` si pertenece a esa clase (si no, ``None``)."""
    async with SessionLocal() as session:
        row = (
            await session.execute(
                select(Analysis, Repository)
                .join(Repository, Analysis.repository_id == Repository.id)
                .where(
                    Analysis.id == analysis_id,
                    Repository.org == org,
                    Repository.classroom == classroom,
                )
            )
        ).first()
    if row is None:
        return None
    analysis, repo = row
    try:
        payload = json.loads(analysis.feedback_json)
    except json.JSONDecodeError:
        payload = {}
    text = _feedback_text(payload) if isinstance(payload, dict) else ""
    tests = payload.get("tests") if isinstance(payload, dict) else None
    if isinstance(tests, dict):
        failing = [
            str(t.get("name"))
            for t in tests.get("tests", [])
            if isinstance(t, dict) and not t.get("passed")
        ]
        text += f" Tests: pasan {tests.get('passed')} de {tests.get('total')}."
        if failing:
            text += f" Fallan: {', '.join(failing)}."
    return Correction(
        analysis_id=analysis.id,
        assignment=repo.assignment,
        owner=repo.owner,
        commit_sha=analysis.commit_sha,
        passage=Passage(
            source="correccion",
            title=f"Esta corrección de {repo.assignment} ({analysis.commit_sha[:7]})",
            heading=None,
            text=text.strip() or "Corrección sin feedback estructurado.",
            score=10.0,  # siempre la primera fuente: la duda es sobre ella
            ref=f"analysis-{analysis.id}",
        ),
    )


def _feedback_text(payload: dict[str, object]) -> str:
    parts = [str(payload.get(key, "")) for key in ("funcionalidad", "calidad", "diseno")]
    pista = payload.get("pista")
    if isinstance(pista, dict) and pista.get("text"):
        parts.append(f"Pista: {pista['text']}")
    return " ".join(p for p in parts if p)


async def _own_feedback(
    org: str, classroom: str, login: str, question: str, assignment: str | None
) -> list[Passage]:
    """Últimos análisis del propio alumno en esa clase, puntuados frente a la pregunta."""
    async with SessionLocal() as session:
        stmt = (
            select(Analysis, Repository)
            .join(Repository, Analysis.repository_id == Repository.id)
            .where(
                Repository.org == org,
                Repository.classroom == classroom,
                func.lower(Repository.owner) == login.lower(),
            )
            .order_by(Analysis.created_at.desc())
            .limit(12)
        )
        rows = (await session.execute(stmt)).all()
    embedder = get_embedder()
    vector = embedder.embed(question)
    words = set(tokens(question))
    passages: list[Passage] = []
    for analysis, repo in rows:
        try:
            payload = json.loads(analysis.feedback_json)
        except json.JSONDecodeError:
            continue
        text = _feedback_text(payload) if isinstance(payload, dict) else ""
        if not text:
            continue
        overlap = len(words & set(tokens(text)))
        if not overlap:
            continue  # sin palabras en común no es relevante, aunque sea de su entrega
        score = cosine(vector, embedder.embed(text)) + 0.05 * overlap
        if assignment and repo.assignment == assignment:
            score += 0.1  # la duda es sobre esta entrega
        passages.append(
            Passage(
                source="feedback",
                title=f"Tu feedback de {repo.assignment} ({analysis.commit_sha[:7]})",
                heading=None,
                text=text,
                score=score,
                ref=f"analysis-{analysis.id}",
            )
        )
    passages.sort(key=lambda p: p.score, reverse=True)
    return [p for p in passages[:2] if p.score > 0.08]


def _diverse(passages: list[Passage], *, limit: int) -> list[Passage]:
    """El mejor fragmento de cada fuente (material, feedback, guía) y luego por puntuación."""
    ranked = sorted(passages, key=lambda p: p.score, reverse=True)
    picked: list[Passage] = []
    for source in ("material", "feedback", "zuzenaa"):
        best = next((p for p in ranked if p.source == source), None)
        if best is not None:
            picked.append(best)
    picked += [p for p in ranked if p not in picked]
    return sorted(picked[:limit], key=lambda p: p.score, reverse=True)


async def ask(
    *,
    org: str,
    classroom: str,
    question: str,
    login: str | None,
    assignment: str | None = None,
    correction: Correction | None = None,
) -> TutorReply:
    """``login`` = alumno cuya duda se responde (``None``: profesorado sin alumno).

    Con ``correction`` (abierto desde una corrección), esa corrección es siempre la
    primera fuente y el resto se busca alrededor de ella.
    """
    tutor = get_tutor()
    question = question.strip()[:MAX_QUESTION_CHARS]
    terms: list[str] = []
    alias = "alumno"
    if login is not None:
        alias = await pseudonyms.alias_for(org, classroom, login)
        terms = await pseudonyms.personal_terms(org, classroom, login)
    clean_question = str(scrub(question, terms, alias))

    topic = topic_only(clean_question)
    passages = await store.search(org, classroom, topic, k=4)
    if login is not None:
        passages += await _own_feedback(org, classroom, login, topic, assignment)
    if correction is not None:
        passages = [p for p in passages if p.ref != correction.passage.ref]
        # La corrección + lo mejor del material y de otra fuente (se muestran 3 en total).
        passages = [correction.passage, *_diverse(passages, limit=2)]
    else:
        passages = _diverse(passages, limit=4)
    for passage in passages:
        passage.text = str(scrub(passage.text, terms, alias))
        passage.title = str(scrub(passage.title, terms, alias))

    # Nada personal hacia el proveedor (aunque hoy sea local).
    if leaks([clean_question, [(p.title, p.heading or "", p.text) for p in passages]], terms):
        return TutorReply(answer=BLOCKED, citations=[], blocked=True, provider=tutor.name)

    answer = await tutor.answer(question=clean_question, passages=passages)
    if not is_safe(answer):
        return TutorReply(answer=BLOCKED, citations=[], blocked=True, provider=tutor.name)

    citations = [
        Citation(
            number=number,
            source=p.source,
            title=p.title,
            heading=p.heading,
            snippet=p.text[:240],
            ref=p.ref,
        )
        for number, p in enumerate(passages[:3], start=1)
        if f"[{number}]" in answer
    ]
    return TutorReply(answer=answer, citations=citations, blocked=False, provider=tutor.name)


__all__ = ["BLOCKED", "Citation", "Correction", "TutorReply", "ask", "load_correction"]
