"""Agent worker: gather context, call the provider, guardrail, render, comment."""

from __future__ import annotations

from dataclasses import dataclass

from zuzenaa.agent import guardrails
from zuzenaa.agent.llm import LlmProvider, parse_feedback
from zuzenaa.agent.schema import AgentFeedback

MARKER = "<!-- zuzenaa-agent -->"


@dataclass
class AgentResult:
    posted: bool
    provider: str
    body: str
    reason: str | None = None
    feedback: AgentFeedback | None = None


_PROMPT = """\
Eres un tutor de programación. A partir del contexto y el diff, escribe feedback
pedagógico BREVE en castellano para el alumnado. No des código, no des la
solución, no reescribas su trabajo. Orienta con una pista.

Devuelve SOLO un JSON con esta forma:
{"funcionalidad": str, "calidad": str, "diseno": str,
 "pista": {"level": int, "text": str}, "teoria": str | null}
"""


class AgentWorker:
    def __init__(self, provider: LlmProvider) -> None:
        self.provider = provider

    async def analyze(self, context: dict[str, object]) -> AgentFeedback:
        raw = await self.provider.generate(prompt=_PROMPT, context=context)
        feedback = parse_feedback(raw)
        guardrails.enforce(feedback)
        return feedback

    @staticmethod
    def render(feedback: AgentFeedback) -> str:
        """Render validated feedback to Markdown (never raw model text)."""
        lines = [
            MARKER,
            "**Feedback automático de ZuzenAA**",
            "",
            f"**Funcionalidad**  \n{feedback.funcionalidad}",
            "",
            f"**Calidad**  \n{feedback.calidad}",
            "",
            f"**Diseño**  \n{feedback.diseno}",
            "",
            f"**Pista (nivel {feedback.pista.level})**  \n{feedback.pista.text}",
        ]
        if feedback.teoria:
            lines += ["", f"**Teoría relacionada**  \n{feedback.teoria}"]
        lines += [
            "",
            "> Este comentario orienta, no resuelve. No contiene la solución.",
        ]
        return "\n".join(lines)

    async def run(self, context: dict[str, object]) -> AgentResult:
        try:
            feedback = await self.analyze(context)
        except guardrails.GuardrailViolation as exc:
            return AgentResult(
                posted=False, provider=self.provider.name, body="", reason=exc.reason
            )
        return AgentResult(
            posted=True,
            provider=self.provider.name,
            body=self.render(feedback),
            feedback=feedback,
        )
