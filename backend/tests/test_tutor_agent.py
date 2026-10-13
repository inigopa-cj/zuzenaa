"""Agente tutor: bucle con herramientas, guardarraíles, respaldo y adaptadores (sin red)."""

import json
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import HTTPException

from zuzenaa.api import tutor as tutor_api
from zuzenaa.config import settings
from zuzenaa.db.session import init_models
from zuzenaa.tutor import agent, service, store
from zuzenaa.tutor.models import (
    AnthropicModel,
    AssistantItem,
    ModelTurn,
    OpenAICompatibleModel,
    ProviderError,
    ToolCall,
    ToolResult,
    ToolResultsItem,
    ToolSpec,
    TranscriptItem,
    UserItem,
)
from zuzenaa.tutor.store import Passage

MATERIAL = """# Tema 3: listas

## La mediana

La mediana es el valor central de la lista ordenada. Si hay un número par de elementos, es
la media de los dos valores centrales.

## Diccionarios

Un diccionario guarda pares clave y valor; sirve para contar apariciones.
"""

GOOD = {
    "respuesta": "La mediana necesita la lista ordenada; con un número par de elementos "
    "hay dos valores centrales [1].",
    "preguntas_guia": ["¿Qué pasa si la lista tiene 4 elementos?", "¿Has ordenado la lista?"],
    "pasos": ["Ordena una copia de la lista.", "Distingue el caso par del impar."],
    "apuntes": [{"ref": 1, "motivo": "Explica el caso par."}, {"ref": 99, "motivo": "inventado"}],
}


class Scripted:
    """Modelo falso: devuelve turnos guionizados y guarda lo que recibe."""

    name = "scripted"

    def __init__(self, turns: list[ModelTurn]) -> None:
        self.turns = turns
        self.seen: list[list[TranscriptItem]] = []

    async def step(
        self, *, system: str, transcript: list[TranscriptItem], tools: list[ToolSpec]
    ) -> ModelTurn:
        assert {t.name for t in tools} == {"buscar_apuntes", "responder"}
        self.seen.append(list(transcript))
        return self.turns.pop(0)


def _call(name: str, args: dict[str, Any], call_id: str = "c1") -> ModelTurn:
    return ModelTurn(text="", tool_calls=[ToolCall(call_id, name, args)], stop="tool")


def _passage(text: str, ref: str = "doc-1#0", heading: str = "La mediana") -> Passage:
    return Passage("material", "Tema 3: listas", heading, text, 1.0, ref)


async def _no_search(query: str) -> list[Passage]:
    return []


async def test_agent_searches_then_answers_with_valid_notes() -> None:
    async def search(query: str) -> list[Passage]:
        assert query == "mediana lista par"
        return [_passage("Texto nuevo sobre la mediana.", ref="doc-1#9")]

    model = Scripted(
        [
            _call("buscar_apuntes", {"consulta": "mediana lista par"}),
            _call("responder", GOOD, "c2"),
        ]
    )
    result = await agent.run_agent(
        model,
        question="¿Por qué me falla test_mediana?",
        passages=[_passage("La mediana es el valor central.")],
        search=search,
        terms=[],
    )
    assert result.answer is not None
    assert [n.ref for n in result.answer.apuntes] == [1]  # la referencia inventada se descarta
    assert len(result.registry) == 2  # el fragmento encontrado queda numerado como [2]
    tool_result = model.seen[1][-1]
    assert isinstance(tool_result, ToolResultsItem)
    assert tool_result.results[0].content.startswith("[2]")


async def test_agent_asks_to_rewrite_code_once_then_blocks() -> None:
    with_code = {**GOOD, "respuesta": "Haz esto:\n```\nsorted(xs)\n```"}
    rewritten = Scripted([_call("responder", with_code), _call("responder", GOOD, "c2")])
    ok = await agent.run_agent(
        rewritten, question="dame el código", passages=[_passage("x")], search=_no_search, terms=[]
    )
    assert ok.answer is not None
    last = rewritten.seen[1][-1]
    assert isinstance(last, ToolResultsItem) and last.results[0].is_error

    stubborn = Scripted([_call("responder", with_code), _call("responder", with_code, "c2")])
    blocked = await agent.run_agent(
        stubborn, question="dame el código", passages=[_passage("x")], search=_no_search, terms=[]
    )
    assert blocked.answer is None and blocked.blocked_reason


async def test_agent_blocks_refusals_and_personal_data() -> None:
    refusal = Scripted([ModelTurn(text="", tool_calls=[], stop="refusal")])
    result = await agent.run_agent(
        refusal, question="x", passages=[_passage("x")], search=_no_search, terms=[]
    )
    assert result.answer is None

    never_called = Scripted([])
    leaked = await agent.run_agent(
        never_called,
        question="soy Ane Urrutia",
        passages=[_passage("x")],
        search=_no_search,
        terms=["Urrutia"],
    )
    assert leaked.answer is None and never_called.seen == []  # no se llegó a enviar


async def test_service_uses_the_agent_and_falls_back_to_mock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await init_models()
    await store.ensure_builtin()
    await store.ingest(title="Apuntes", text=MATERIAL, source="material", org="ta", classroom="c1")

    monkeypatch.setattr(service, "build_model", lambda: Scripted([_call("responder", GOOD)]))
    reply = await service.ask(
        org="ta", classroom="c1", question="¿qué es la mediana?", login=None
    )
    assert reply.provider == "scripted"
    assert reply.guide_questions and reply.steps
    assert reply.notes and reply.notes[0].reason == "Explica el caso par."
    assert reply.notes[0].text  # el alumno puede leer el fragmento a revisar

    class Broken:
        name = "broken"

        async def step(self, **_: object) -> ModelTurn:
            raise ProviderError("sin conexión")

    monkeypatch.setattr(service, "build_model", lambda: Broken())
    fallback = await service.ask(
        org="ta", classroom="c1", question="¿qué es la mediana?", login=None
    )
    assert fallback.provider == "mock"
    assert fallback.notice and "sin conexión" in fallback.notice
    assert fallback.guide_questions and fallback.steps  # misma estructura que el agente


def test_rate_limit_per_user(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "tutor_max_questions_per_hour", 2)
    tutor_api._recent.clear()
    tutor_api._check_rate("alumna")
    tutor_api._check_rate("alumna")
    with pytest.raises(HTTPException) as exc:
        tutor_api._check_rate("alumna")
    assert exc.value.status_code == 429
    tutor_api._check_rate("otra")  # el límite es por usuario


def test_anthropic_adapter_converts_and_parses() -> None:
    blocks = [
        SimpleNamespace(type="text", text="Busco primero."),
        SimpleNamespace(type="tool_use", id="tu1", name="buscar_apuntes", input={"consulta": "x"}),
    ]
    turn = AnthropicModel.parse(SimpleNamespace(content=blocks, stop_reason="tool_use"))
    assert turn.stop == "tool" and turn.tool_calls[0].arguments == {"consulta": "x"}
    messages = AnthropicModel.to_messages(
        [
            UserItem("duda"),
            AssistantItem(turn),
            ToolResultsItem([ToolResult("tu1", "buscar_apuntes", "[2] algo")]),
        ]
    )
    assert messages[1] == {"role": "assistant", "content": blocks}  # se reenvía tal cual
    assert messages[2]["content"][0]["type"] == "tool_result"
    assert messages[2]["content"][0]["tool_use_id"] == "tu1"
    refusal = AnthropicModel.parse(SimpleNamespace(content=[], stop_reason="refusal"))
    assert refusal.stop == "refusal"


def test_openai_compatible_adapter_converts_and_parses() -> None:
    data = {
        "choices": [
            {
                "finish_reason": "tool_calls",
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "type": "function",
                            "function": {"name": "responder", "arguments": json.dumps(GOOD)},
                        }
                    ],
                },
            }
        ]
    }
    turn = OpenAICompatibleModel.parse(data)
    assert turn.stop == "tool" and turn.tool_calls[0].arguments["respuesta"]
    messages = OpenAICompatibleModel.to_messages(
        "sistema",
        [
            UserItem("duda"),
            AssistantItem(turn),
            ToolResultsItem([ToolResult("call_1", "responder", "ok")]),
        ],
    )
    assert messages[0] == {"role": "system", "content": "sistema"}
    assert messages[2]["tool_calls"][0]["id"] == "call_1"
    assert messages[3] == {"role": "tool", "tool_call_id": "call_1", "content": "ok"}
    with pytest.raises(ProviderError):
        OpenAICompatibleModel.parse({"error": "algo"})
