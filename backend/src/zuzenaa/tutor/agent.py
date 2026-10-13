"""Bucle del agente tutor: busca en los apuntes y responde de forma estructurada.

El agente recibe la duda (ya limpia) y unos fragmentos numerados (la corrección desde
la que se abrió, apuntes de la clase, guía de ZuzenAA y el feedback del alumno). Tiene
dos herramientas:

- ``buscar_apuntes``: busca más fragmentos si los iniciales no bastan (máx. 2 veces);
- ``responder``: entrega la respuesta final, estructurada (explicación, preguntas guía,
  pasos y qué apuntes revisar).

Guardarraíles: la respuesta se valida contra el esquema y se revisa con las mismas
reglas que el feedback del agente (sin código ni soluciones copiables). Si incumple, se
le pide reescribirla una vez; si vuelve a incumplir, se bloquea. Antes de cada llamada
se comprueba que no viaje ningún dato personal.
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from pydantic import BaseModel, Field, ValidationError

from zuzenaa.agent import guardrails
from zuzenaa.privacy.scrub import leaks
from zuzenaa.tutor.models import (
    AssistantItem,
    ChatModel,
    ProviderError,
    ToolResult,
    ToolResultsItem,
    ToolSpec,
    TranscriptItem,
    UserItem,
)
from zuzenaa.tutor.store import Passage

MAX_STEPS = 6
MAX_SEARCHES = 2
MAX_REWRITES = 1

SYSTEM_PROMPT = """\
Eres el tutor de programación de una clase de Formación Profesional. Respondes en
castellano, con un tono cercano y claro, a un alumno identificado solo por su código.

Tu objetivo es que el alumno aprenda a resolver el problema por sí mismo:
- Explica el concepto o el motivo del fallo con palabras. Puedes explicar cómo se
  resuelve el problema (la idea, el razonamiento, qué caso falta por contemplar), pero
  NUNCA escribas código: ni bloques de código, ni líneas de código, ni pseudocódigo
  copiable, ni el nombre exacto de la instrucción que lo arreglaría si eso equivale a
  darle la línea hecha.
- Hazle pensar: plantea preguntas guía concretas que le lleven a la solución.
- Propón pasos para abordarlo, descritos en lenguaje natural.
- Indícale qué apuntes debe revisar y por qué, usando SOLO los fragmentos numerados
  que tienes ([n]). Prioriza los apuntes de la clase.

Basa tu respuesta en los fragmentos. Si no bastan, usa la herramienta buscar_apuntes
con otras palabras (como mucho dos veces). Si el material no cubre la duda, dilo con
sinceridad y sugiere preguntar al profesorado. No inventes apuntes ni secciones.

Termina SIEMPRE llamando a la herramienta responder. La explicación debe ser breve
(como mucho unas 150 palabras), con 2 o 3 preguntas guía y entre 2 y 4 pasos.
Nunca pidas ni menciones datos personales del alumno.
"""

SEARCH_TOOL = ToolSpec(
    name="buscar_apuntes",
    description=(
        "Busca más fragmentos en los apuntes de la clase, la guía de ZuzenAA y el feedback "
        "del alumno. Devuelve fragmentos numerados que puedes citar como [n]."
    ),
    parameters={
        "type": "object",
        "properties": {
            "consulta": {
                "type": "string",
                "description": "Qué buscar, con palabras del tema (no la duda literal).",
            }
        },
        "required": ["consulta"],
        "additionalProperties": False,
    },
)

ANSWER_TOOL = ToolSpec(
    name="responder",
    description="Entrega la respuesta final al alumno. Sin código.",
    parameters={
        "type": "object",
        "properties": {
            "respuesta": {
                "type": "string",
                "description": "Explicación breve, en palabras, sin código.",
            },
            "preguntas_guia": {
                "type": "array",
                "items": {"type": "string"},
                "description": "2 o 3 preguntas que hagan pensar al alumno.",
            },
            "pasos": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Entre 2 y 4 pasos para abordarlo, en lenguaje natural.",
            },
            "apuntes": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "ref": {"type": "integer", "description": "Número [n] del fragmento."},
                        "motivo": {"type": "string", "description": "Por qué debe revisarlo."},
                    },
                    "required": ["ref", "motivo"],
                    "additionalProperties": False,
                },
                "description": "Qué fragmentos debe revisar el alumno y por qué.",
            },
        },
        "required": ["respuesta", "preguntas_guia", "pasos", "apuntes"],
        "additionalProperties": False,
    },
)


class NoteRef(BaseModel):
    ref: int
    motivo: str = Field(max_length=400)


class TutorAnswer(BaseModel):
    respuesta: str = Field(min_length=1, max_length=1500)
    preguntas_guia: list[str] = Field(max_length=5)
    pasos: list[str] = Field(max_length=6)
    apuntes: list[NoteRef] = Field(max_length=6)


SearchFn = Callable[[str], Awaitable[list[Passage]]]


@dataclass
class AgentResult:
    answer: TutorAnswer | None
    registry: list[Passage] = field(default_factory=list)
    blocked_reason: str | None = None


def _render(number: int, passage: Passage) -> str:
    label = {
        "correccion": "Corrección",
        "material": "Apuntes",
        "feedback": "Feedback del alumno",
        "zuzenaa": "Guía de ZuzenAA",
    }.get(passage.source, passage.source)
    where = passage.title + (f" / {passage.heading}" if passage.heading else "")
    return f"[{number}] ({label}) {where}:\n{passage.text}"


def _violation(answer: TutorAnswer) -> str | None:
    texts = [answer.respuesta, *answer.preguntas_guia, *answer.pasos]
    texts += [note.motivo for note in answer.apuntes]
    for text in texts:
        reason = guardrails.text_violation(text)
        if reason:
            return reason
    return None


async def run_agent(
    model: ChatModel,
    *,
    question: str,
    passages: list[Passage],
    search: SearchFn,
    terms: list[str],
) -> AgentResult:
    """Ejecuta el agente. ``terms`` = datos personales que nunca deben viajar."""
    registry = list(passages)
    context = "\n\n".join(_render(i, p) for i, p in enumerate(registry, start=1))
    transcript: list[TranscriptItem] = [
        UserItem(
            f"Duda del alumno:\n{question}\n\n"
            f"Fragmentos disponibles:\n{context or '(ninguno todavía)'}"
        )
    ]
    tools = [SEARCH_TOOL, ANSWER_TOOL]
    searches = rewrites = nudges = 0

    for _ in range(MAX_STEPS):
        if leaks([_transcript_text(transcript)], terms):
            return AgentResult(None, registry, "el contexto contenía datos personales")
        turn = await model.step(system=SYSTEM_PROMPT, transcript=transcript, tools=tools)
        transcript.append(AssistantItem(turn))
        if turn.stop == "refusal":
            return AgentResult(None, registry, "el modelo ha rechazado la petición")

        if not turn.tool_calls:
            if nudges:
                raise ProviderError("el modelo no ha entregado una respuesta estructurada")
            nudges += 1
            transcript.append(UserItem("Entrega tu respuesta llamando a la herramienta responder."))
            continue

        results: list[ToolResult] = []
        final: TutorAnswer | None = None
        for call in turn.tool_calls:
            if call.name == SEARCH_TOOL.name:
                results.append(await _search(call.id, call.arguments, registry, search, searches))
                searches += 1
                continue
            if call.name != ANSWER_TOOL.name:
                results.append(ToolResult(call.id, call.name, "Herramienta desconocida.", True))
                continue
            try:
                answer = TutorAnswer.model_validate(call.arguments)
            except ValidationError:
                results.append(
                    ToolResult(call.id, call.name, "La respuesta no cumple el esquema.", True)
                )
                continue
            reason = _violation(answer)
            if reason is None:
                answer.apuntes = [
                    note for note in answer.apuntes if 1 <= note.ref <= len(registry)
                ]
                final = answer
                results.append(ToolResult(call.id, call.name, "Respuesta entregada."))
                continue
            if rewrites >= MAX_REWRITES:
                return AgentResult(None, registry, f"la respuesta {reason}")
            rewrites += 1
            results.append(
                ToolResult(
                    call.id,
                    call.name,
                    f"Rechazada: la respuesta {reason}. Reescríbela sin ningún código: "
                    "explica la idea con palabras y vuelve a llamar a responder.",
                    True,
                )
            )
        if final is not None:
            return AgentResult(final, registry)
        transcript.append(ToolResultsItem(results))

    raise ProviderError("el agente no ha terminado en el número de pasos previsto")


async def _search(
    call_id: str,
    arguments: dict[str, object],
    registry: list[Passage],
    search: SearchFn,
    done: int,
) -> ToolResult:
    if done >= MAX_SEARCHES:
        enough = "Ya has buscado suficiente: responde con lo que tienes."
        return ToolResult(call_id, SEARCH_TOOL.name, enough, True)
    query = str(arguments.get("consulta", "")).strip()[:300]
    found = [p for p in await search(query) if p.ref not in {r.ref for r in registry}]
    if not found:
        return ToolResult(call_id, SEARCH_TOOL.name, "Sin resultados nuevos.")
    start = len(registry) + 1
    registry.extend(found)
    rendered = "\n\n".join(_render(start + i, p) for i, p in enumerate(found))
    return ToolResult(call_id, SEARCH_TOOL.name, rendered)


def _transcript_text(transcript: list[TranscriptItem]) -> str:
    """Todo el texto que vamos a enviar (para comprobar que no hay datos personales)."""
    parts: list[str] = []
    for item in transcript:
        if isinstance(item, UserItem):
            parts.append(item.text)
        elif isinstance(item, ToolResultsItem):
            parts.extend(r.content for r in item.results)
        else:
            parts.append(item.turn.text)
            parts.extend(json.dumps(c.arguments, ensure_ascii=False) for c in item.turn.tool_calls)
    return "\n".join(parts)


__all__ = [
    "ANSWER_TOOL",
    "MAX_SEARCHES",
    "SEARCH_TOOL",
    "SYSTEM_PROMPT",
    "AgentResult",
    "NoteRef",
    "TutorAnswer",
    "run_agent",
]
