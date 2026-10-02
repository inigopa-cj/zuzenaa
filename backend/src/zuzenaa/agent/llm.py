"""LLM providers.

`LlmProvider` is the seam: swap the mock for OpenAI/Anthropic/local without
touching the worker. The mock is deterministic and always guardrail-safe, so the
whole flow (web → backend → provider → feedback → comment) can run with no key.
"""

from __future__ import annotations

import json
from typing import Protocol

from zuzenaa.agent.schema import AgentFeedback, Hint


class LlmProvider(Protocol):
    name: str

    async def generate(self, *, prompt: str, context: dict[str, object]) -> str:
        """Return raw text expected to contain a JSON AgentFeedback object."""
        ...


def _as_int(value: object) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return 0


def _as_str_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str)]
    return []


class MockProvider:
    """Deterministic provider for local/dev and tests.

    It reads the *real* repository context built by ``agent.context`` (file tree,
    language mix, size signals, diff) and returns a short, solution-free
    summary, so the end-to-end flow is observable and code-aware without a model.
    """

    name = "mock"

    async def generate(self, *, prompt: str, context: dict[str, object]) -> str:
        repo = context.get("repo")
        feedback = (
            self._from_repo(repo, context) if isinstance(repo, dict) else self._generic()
        )
        return feedback.model_dump_json()

    @staticmethod
    def _generic() -> AgentFeedback:
        return AgentFeedback(
            funcionalidad="Todavía no hay código descargado que resumir.",
            calidad="Revisa el estilo y los nombres para que el código se lea con facilidad.",
            diseno=(
                "Comprueba si alguna función concentra demasiada responsabilidad "
                "y valora separarla."
            ),
            pista=Hint(
                level=2,
                text="Piensa qué ocurre con entradas vacías antes de operar con la colección.",
            ),
            teoria=None,
        )

    @staticmethod
    def _from_repo(repo: dict[str, object], context: dict[str, object]) -> AgentFeedback:
        file_count = _as_int(repo.get("file_count"))
        line_count = _as_int(repo.get("line_count"))
        languages = _as_str_list(repo.get("languages"))
        has_tests = bool(repo.get("has_tests"))
        has_readme = bool(repo.get("has_readme"))
        todo_count = _as_int(repo.get("todo_count"))
        top = MockProvider._largest(repo)
        diff = repo.get("diff")

        if isinstance(diff, dict):
            files_changed = _as_int(diff.get("files_changed"))
            insertions = _as_int(diff.get("insertions"))
            deletions = _as_int(diff.get("deletions"))
            funcionalidad = (
                f"En esta revisión has tocado {files_changed} fichero(s), "
                f"con {insertions} línea(s) añadidas y {deletions} eliminadas."
            )
            evolution = context.get("evolution")
            if isinstance(evolution, str) and evolution:
                funcionalidad += f" {evolution}"
        else:
            lang_text = ", ".join(languages) if languages else "sin lenguaje detectado"
            funcionalidad = (
                f"El proyecto tiene {file_count} fichero(s) y unas {line_count} líneas "
                f"({lang_text})."
            )

        quality: list[str] = []
        if not has_readme:
            quality.append("Añade un README que explique cómo ejecutar el proyecto.")
        if not has_tests:
            quality.append(
                "No se ve una carpeta de pruebas: separa la lógica para poder probarla."
            )
        else:
            quality.append("Ya hay pruebas: añade un caso que todavía no cubras.")
        if todo_count:
            quality.append(f"Quedan {todo_count} marca(s) TODO/FIXME por resolver.")
        quality.append("Cuida que los nombres de variables y funciones describan su intención.")
        calidad = " ".join(quality)

        diseno = "Divide el código en funciones pequeñas con una única responsabilidad."
        if top is not None:
            diseno = (
                f"El fichero '{top[0]}' es el más grande ({top[1]} líneas): "
                "valora si concentra demasiadas responsabilidades."
            )

        return AgentFeedback(
            funcionalidad=funcionalidad,
            calidad=calidad,
            diseno=diseno,
            pista=Hint(
                level=2,
                text="Prueba el caso límite de una entrada vacía antes de recorrer la colección.",
            ),
            teoria=None,
        )

    @staticmethod
    def _largest(repo: dict[str, object]) -> tuple[str, int] | None:
        largest = repo.get("largest_files")
        if not isinstance(largest, list) or not largest:
            return None
        top = largest[0]
        if not isinstance(top, dict):
            return None
        path = top.get("path")
        if not isinstance(path, str) or not path:
            return None
        return path, _as_int(top.get("lines"))


def build_provider(provider: str, **_: object) -> LlmProvider:
    """Return a provider by name. Only the mock is implemented for now."""
    if provider in {"mock", "none", ""}:
        return MockProvider()
    raise ValueError(
        f"proveedor LLM no soportado todavía: {provider!r} "
        "(por ahora solo 'mock'; OpenAI/Anthropic/local llegarán detrás de esta interfaz)"
    )


def get_provider() -> LlmProvider:
    from zuzenaa.config import settings

    return build_provider(settings.llm_provider)


def parse_feedback(raw: str) -> AgentFeedback:
    """Parse the provider's raw output into the typed schema."""
    payload = json.loads(raw)
    return AgentFeedback.model_validate(payload)
