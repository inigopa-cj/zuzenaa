"""Modelos de lenguaje del agente tutor, detrás de una interfaz neutra.

El bucle del agente (``tutor/agent.py``) habla con ``ChatModel`` en un formato propio
(transcripción neutra + herramientas); cada adaptador lo traduce a su API:

- ``AnthropicModel``: SDK oficial de Anthropic (``anthropic``), Messages API con
  herramientas. En los modelos que lo admiten activa los *fallbacks* del servidor
  (si el modelo rechaza una petición, la API la reintenta con otro modelo).
- ``OpenAICompatibleModel``: cualquier proveedor con ``/chat/completions`` compatible
  con OpenAI (OpenAI, Mistral...), por HTTP.

Se elige con ``ZUZENAA_TUTOR_PROVIDER``. Al proveedor solo llega texto ya
seudonimizado y limpio (``tutor/service.py``); ningún dato personal sale del servidor.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, cast

import httpx

from zuzenaa.config import settings


class ProviderError(RuntimeError):
    """El proveedor no está disponible o ha fallado: el tutor vuelve al mock."""


@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema (additionalProperties: false, todo required)


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


Stop = Literal["end", "tool", "refusal", "max_tokens"]


@dataclass
class ModelTurn:
    text: str
    tool_calls: list[ToolCall]
    stop: Stop
    raw: Any = None  # mensaje del proveedor tal cual, para reenviarlo en el siguiente paso


@dataclass
class UserItem:
    text: str


@dataclass
class AssistantItem:
    turn: ModelTurn


@dataclass
class ToolResult:
    call_id: str
    name: str
    content: str
    is_error: bool = False


@dataclass
class ToolResultsItem:
    results: list[ToolResult] = field(default_factory=list)


TranscriptItem = UserItem | AssistantItem | ToolResultsItem


class ChatModel(Protocol):
    name: str

    async def step(
        self, *, system: str, transcript: list[TranscriptItem], tools: list[ToolSpec]
    ) -> ModelTurn: ...


# --- Anthropic (SDK oficial) ------------------------------------------------------

# Modelos que aceptan los fallbacks del servidor en su forma "default" (Claude API).
_FALLBACK_MODELS = frozenset(
    {"claude-fable-5-1", "claude-opus-5-5", "claude-opus-5", "claude-sonnet-5-5"}
)
_FALLBACK_BETA = "server-side-fallback-2026-07-01"


class AnthropicModel:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str | None = None,
        effort: str = "low",
        max_tokens: int = 4000,
        timeout: float = 60.0,
        workspace_id: str | None = None,
    ) -> None:
        import anthropic

        self.name = f"anthropic:{model}"
        self.model = model
        self.effort = effort
        self.max_tokens = max_tokens
        self._anthropic = anthropic
        # Claves no asociadas a un workspace: la API exige la cabecera con su ID.
        headers = {"anthropic-workspace-id": workspace_id} if workspace_id else None
        self._client = anthropic.AsyncAnthropic(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout,
            max_retries=2,
            default_headers=headers,
        )
        # Los fallbacks del servidor solo existen en la Claude API (sin base_url propia).
        self._fallbacks = base_url is None and model in _FALLBACK_MODELS

    @staticmethod
    def to_messages(transcript: list[TranscriptItem]) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = []
        for item in transcript:
            if isinstance(item, UserItem):
                messages.append({"role": "user", "content": item.text})
            elif isinstance(item, AssistantItem):
                # El contenido se reenvía tal cual (bloques de thinking incluidos).
                messages.append({"role": "assistant", "content": item.turn.raw})
            else:
                messages.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": r.call_id,
                                "content": r.content,
                                "is_error": r.is_error,
                            }
                            for r in item.results
                        ],
                    }
                )
        return messages

    @staticmethod
    def parse(response: Any) -> ModelTurn:
        text = "".join(b.text for b in response.content if b.type == "text")
        calls = [
            ToolCall(id=b.id, name=b.name, arguments=dict(b.input))
            for b in response.content
            if b.type == "tool_use"
        ]
        reason = response.stop_reason
        stop: Stop = (
            "tool"
            if reason == "tool_use"
            else "refusal"
            if reason == "refusal"
            else "max_tokens"
            if reason == "max_tokens"
            else "end"
        )
        return ModelTurn(text=text, tool_calls=calls, stop=stop, raw=response.content)

    async def step(
        self, *, system: str, transcript: list[TranscriptItem], tools: list[ToolSpec]
    ) -> ModelTurn:
        anthropic = self._anthropic
        params: dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "system": system,
            "messages": self.to_messages(transcript),
            "tools": [
                {
                    "name": t.name,
                    "description": t.description,
                    "input_schema": t.parameters,
                    "strict": True,
                }
                for t in tools
            ],
            "cache_control": {"type": "ephemeral"},  # sistema + herramientas son estables
        }
        if self.effort:
            params["output_config"] = {"effort": self.effort}
        try:
            if self._fallbacks:
                response = await self._client.beta.messages.create(
                    betas=[_FALLBACK_BETA], fallbacks="default", **params
                )
            else:
                response = await self._client.messages.create(**cast(Any, params))
        except anthropic.AuthenticationError as exc:
            raise ProviderError("clave de API de Anthropic no válida") from exc
        except anthropic.RateLimitError as exc:
            raise ProviderError("límite de uso de la API de Anthropic alcanzado") from exc
        except anthropic.BadRequestError as exc:
            hint = " (falta ZUZENAA_TUTOR_WORKSPACE_ID)" if "workspace" in str(exc.message) else ""
            raise ProviderError(f"la API de Anthropic rechazó la petición (400){hint}") from exc
        except anthropic.APIStatusError as exc:
            raise ProviderError(f"error de la API de Anthropic ({exc.status_code})") from exc
        except anthropic.APIConnectionError as exc:
            raise ProviderError("no se pudo conectar con la API de Anthropic") from exc
        return self.parse(response)


# --- Compatible con OpenAI (HTTP) ---------------------------------------------------


class OpenAICompatibleModel:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str,
        max_tokens: int = 4000,
        timeout: float = 60.0,
    ) -> None:
        self.name = f"openai_compatible:{model}"
        self.model = model
        self.url = base_url.rstrip("/") + "/chat/completions"
        self.api_key = api_key
        self.max_tokens = max_tokens
        self.timeout = timeout

    @staticmethod
    def to_messages(system: str, transcript: list[TranscriptItem]) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = [{"role": "system", "content": system}]
        for item in transcript:
            if isinstance(item, UserItem):
                messages.append({"role": "user", "content": item.text})
            elif isinstance(item, AssistantItem):
                raw = item.turn.raw if isinstance(item.turn.raw, dict) else {}
                message: dict[str, Any] = {"role": "assistant", "content": raw.get("content")}
                if raw.get("tool_calls"):
                    message["tool_calls"] = raw["tool_calls"]
                messages.append(message)
            else:
                messages.extend(
                    {"role": "tool", "tool_call_id": r.call_id, "content": r.content}
                    for r in item.results
                )
        return messages

    @staticmethod
    def parse(data: dict[str, Any]) -> ModelTurn:
        try:
            choice = data["choices"][0]
            message = choice["message"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError("respuesta del proveedor con un formato inesperado") from exc
        calls: list[ToolCall] = []
        for call in message.get("tool_calls") or []:
            function = call.get("function", {})
            try:
                arguments = json.loads(function.get("arguments") or "{}")
            except json.JSONDecodeError:
                arguments = {}
            calls.append(
                ToolCall(
                    id=str(call.get("id")),
                    name=str(function.get("name")),
                    arguments=arguments if isinstance(arguments, dict) else {},
                )
            )
        reason = choice.get("finish_reason")
        stop: Stop = (
            "tool"
            if calls or reason == "tool_calls"
            else "max_tokens"
            if reason == "length"
            else "refusal"
            if reason == "content_filter"
            else "end"
        )
        text = message.get("content") or ""
        return ModelTurn(text=text, tool_calls=calls, stop=stop, raw=message)

    async def step(
        self, *, system: str, transcript: list[TranscriptItem], tools: list[ToolSpec]
    ) -> ModelTurn:
        body = {
            "model": self.model,
            "messages": self.to_messages(system, transcript),
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.parameters,
                    },
                }
                for t in tools
            ],
            "tool_choice": "auto",
            "max_tokens": self.max_tokens,
            "temperature": 0.3,
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self.url, json=body, headers={"Authorization": f"Bearer {self.api_key}"}
                )
        except httpx.HTTPError as exc:
            raise ProviderError("no se pudo conectar con el proveedor del tutor") from exc
        if response.status_code >= 400:
            raise ProviderError(f"error del proveedor del tutor ({response.status_code})")
        return self.parse(response.json())


def build_model() -> ChatModel | None:
    """El modelo configurado, o ``None`` si el tutor debe usar el mock."""
    provider = settings.tutor_provider
    key = settings.tutor_api_key.get_secret_value() if settings.tutor_api_key else ""
    if provider in {"", "mock", "none"} or not key:
        return None
    if provider == "anthropic":
        return AnthropicModel(
            api_key=key,
            model=settings.tutor_model,
            base_url=settings.tutor_base_url,
            effort=settings.tutor_effort,
            max_tokens=settings.tutor_max_tokens,
            timeout=settings.tutor_timeout,
            workspace_id=settings.tutor_workspace_id,
        )
    if provider == "openai_compatible":
        if not settings.tutor_base_url:
            raise ProviderError("falta ZUZENAA_TUTOR_BASE_URL para el proveedor openai_compatible")
        return OpenAICompatibleModel(
            api_key=key,
            model=settings.tutor_model,
            base_url=settings.tutor_base_url,
            max_tokens=settings.tutor_max_tokens,
            timeout=settings.tutor_timeout,
        )
    raise ProviderError(f"proveedor del tutor desconocido: {provider!r}")


__all__ = [
    "AnthropicModel",
    "AssistantItem",
    "ChatModel",
    "ModelTurn",
    "OpenAICompatibleModel",
    "ProviderError",
    "ToolCall",
    "ToolResult",
    "ToolResultsItem",
    "ToolSpec",
    "TranscriptItem",
    "UserItem",
    "build_model",
]
