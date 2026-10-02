"""Agent worker: feedback generation for a submission.

Provider-agnostic. The default provider is a deterministic **mock** so the flow
can be exercised without an LLM key; real providers plug in behind the same
interface. Guardrails validate the structured output before anything is posted.
"""

from zuzenaa.agent.guardrails import GuardrailViolation
from zuzenaa.agent.llm import LlmProvider, MockProvider, build_provider, get_provider
from zuzenaa.agent.schema import AgentFeedback, Hint
from zuzenaa.agent.worker import AgentWorker

__all__ = [
    "AgentFeedback",
    "AgentWorker",
    "GuardrailViolation",
    "Hint",
    "LlmProvider",
    "MockProvider",
    "build_provider",
    "get_provider",
]
