"""Responde una duda del alumnado: recuperación (RAG) + agente tutor + guardarraíles.

1. La pregunta se limpia de datos personales (login/nombre → seudónimo).
2. Recuperación: la corrección desde la que se abre, material de **esa** clase + guía
   de ZuzenAA (``store.search``) y el **feedback del propio alumno**, que se recupera
   en el momento y nunca incluye el de otros.
3. Todo el contexto se limpia y se verifica que no queden datos personales; si
   quedaran, no se envía al proveedor.
4. Con un proveedor configurado responde el **agente** (``tutor/agent.py``): explica,
   plantea preguntas guía, propone pasos e indica qué apuntes revisar, sin código. Sin
   proveedor (o si falla) responde el mock con la misma estructura.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from sqlalchemy import func, select

from zuzenaa.db.models import Analysis, Repository
from zuzenaa.db.session import SessionLocal
from zuzenaa.privacy import pseudonyms
from zuzenaa.privacy.scrub import leaks, scrub
from zuzenaa.tutor import store
from zuzenaa.tutor.agent import AgentResult, run_agent
from zuzenaa.tutor.embeddings import cosine, get_embedder, tokens
from zuzenaa.tutor.models import ProviderError, build_model
from zuzenaa.tutor.provider import MockTutor, is_safe, topic_only
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
class Note:
    """Apunte que el alumno debe revisar, con el motivo y el texto del fragmento."""

    number: int
    source: str
    title: str
    heading: str | None
    reason: str
    text: str
    ref: str


@dataclass
class TutorReply:
    answer: str
    citations: list[Citation]
    blocked: bool
    provider: str
    guide_questions: list[str] = field(default_factory=list)
    steps: list[str] = field(default_factory=list)
    notes: list[Note] = field(default_factory=list)
    notice: str | None = None  # p. ej. «el tutor avanzado no está disponible»


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
    question = question.strip()[:MAX_QUESTION_CHARS]
    terms: list[str] = []
    alias = "alumno"
    if login is not None:
        alias = await pseudonyms.alias_for(org, classroom, login)
        terms = await pseudonyms.personal_terms(org, classroom, login)
    clean_question = str(scrub(question, terms, alias))

    def clean(found: list[Passage]) -> list[Passage]:
        for passage in found:
            passage.text = str(scrub(passage.text, terms, alias))
            passage.title = str(scrub(passage.title, terms, alias))
        return found

    topic = topic_only(clean_question)
    passages = await store.search(org, classroom, topic, k=4)
    if login is not None:
        passages += await _own_feedback(org, classroom, login, topic, assignment)
    if correction is not None:
        passages = [p for p in passages if p.ref != correction.passage.ref]
        # La corrección + lo mejor del material y de otra fuente.
        passages = [correction.passage, *_diverse(passages, limit=2)]
    else:
        passages = _diverse(passages, limit=4)
    passages = clean(passages)

    # Nada personal hacia el proveedor.
    if leaks([clean_question, [(p.title, p.heading or "", p.text) for p in passages]], terms):
        return TutorReply(answer=BLOCKED, citations=[], blocked=True, provider="tutor")

    notice: str | None = None
    try:
        model = build_model()
    except ProviderError as exc:
        model, notice = None, f"Tutor en modo básico: {exc}."
    if model is not None:

        async def search(query: str) -> list[Passage]:
            found = await store.search(org, classroom, query, k=3)
            if login is not None:
                found += await _own_feedback(org, classroom, login, query, assignment)
            return clean(found)

        try:
            result = await run_agent(
                model, question=clean_question, passages=passages, search=search, terms=terms
            )
        except ProviderError as exc:
            notice = f"El tutor avanzado no está disponible ({exc}); respuesta básica."
        else:
            if result.answer is None:
                return TutorReply(
                    answer=BLOCKED, citations=[], blocked=True, provider=model.name
                )
            return _from_agent(result, provider=model.name)

    return await _mock_reply(clean_question, passages, correction, notice=notice)


def _from_agent(result: AgentResult, *, provider: str) -> TutorReply:
    answer = result.answer
    assert answer is not None
    registry = result.registry
    notes = [
        Note(
            number=note.ref,
            source=registry[note.ref - 1].source,
            title=registry[note.ref - 1].title,
            heading=registry[note.ref - 1].heading,
            reason=note.motivo,
            text=registry[note.ref - 1].text,
            ref=registry[note.ref - 1].ref,
        )
        for note in answer.apuntes
    ]
    cited = {note.number for note in notes} | {
        int(n) for n in re.findall(r"\[(\d+)\]", answer.respuesta) if 1 <= int(n) <= len(registry)
    }
    citations = [
        Citation(
            number=n,
            source=registry[n - 1].source,
            title=registry[n - 1].title,
            heading=registry[n - 1].heading,
            snippet=registry[n - 1].text[:240],
            ref=registry[n - 1].ref,
        )
        for n in sorted(cited)
    ]
    return TutorReply(
        answer=answer.respuesta,
        citations=citations,
        blocked=False,
        provider=provider,
        guide_questions=answer.preguntas_guia,
        steps=answer.pasos,
        notes=notes,
    )


_FAILING = re.compile(r"Fallan?: ([^.]+)\.")


async def _mock_reply(
    question: str,
    passages: list[Passage],
    correction: Correction | None,
    *,
    notice: str | None,
) -> TutorReply:
    """Respuesta sin LLM con la misma estructura que la del agente."""
    tutor = MockTutor()
    answer = await tutor.answer(question=question, passages=passages)
    if not is_safe(answer):
        return TutorReply(answer=BLOCKED, citations=[], blocked=True, provider=tutor.name)
    shown = passages[:3]
    citations = [
        Citation(
            number=number,
            source=p.source,
            title=p.title,
            heading=p.heading,
            snippet=p.text[:240],
            ref=p.ref,
        )
        for number, p in enumerate(shown, start=1)
        if f"[{number}]" in answer
    ]
    notes = [
        Note(
            number=number,
            source=p.source,
            title=p.title,
            heading=p.heading,
            reason=f"Explica «{p.heading or p.title}», relacionado con tu duda.",
            text=p.text,
            ref=p.ref,
        )
        for number, p in enumerate(shown, start=1)
        if p.source in {"material", "zuzenaa"}
    ][:2]
    questions: list[str] = []
    failing = _FAILING.search(correction.passage.text) if correction else None
    if failing:
        test = failing.group(1).split(",")[0].strip()
        questions.append(
            f"¿Qué caso concreto comprueba «{test}»? Escríbelo como un ejemplo de entrada y "
            "la salida que esperas."
        )
    questions.append("¿Qué hace ahora tu programa con ese caso? Síguelo a mano paso a paso.")
    if notes and notes[0].heading:
        questions.append(f"Según «{notes[0].heading}», ¿qué paso o condición te falta?")
    steps = [
        "Relee el apunte indicado y subraya la idea que se aplica a tu caso.",
        "Prueba ese caso con un ejemplo pequeño en tu ordenador.",
        "Ajusta tu código y ejecuta todos los tests antes de volver a subir.",
    ]
    if not passages:
        questions, steps = [], []
    return TutorReply(
        answer=answer,
        citations=citations,
        blocked=False,
        provider=tutor.name,
        guide_questions=questions,
        steps=steps,
        notes=notes,
        notice=notice,
    )


__all__ = ["BLOCKED", "Citation", "Correction", "Note", "TutorReply", "ask", "load_correction"]
