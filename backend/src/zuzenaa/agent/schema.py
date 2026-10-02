"""Structured feedback schema (the LLM must produce this exact shape).

Keeping the model's output typed is what makes the guardrails enforceable: the
renderer never prints raw model text, only validated fields.
"""

from pydantic import BaseModel, ConfigDict


class Hint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    level: int
    text: str


class AgentFeedback(BaseModel):
    model_config = ConfigDict(extra="forbid")

    funcionalidad: str
    calidad: str
    diseno: str
    pista: Hint
    teoria: str | None = None
