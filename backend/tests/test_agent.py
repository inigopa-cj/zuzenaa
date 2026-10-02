import pytest

from zuzenaa.agent import AgentWorker, MockProvider, guardrails
from zuzenaa.agent.llm import build_provider
from zuzenaa.agent.schema import AgentFeedback, Hint
from zuzenaa.agent.worker import MARKER


async def test_mock_provider_is_code_aware() -> None:
    worker = AgentWorker(MockProvider())
    context: dict[str, object] = {
        "evolution": "Análisis anterior en abc1234.",
        "repo": {
            "file_count": 3,
            "line_count": 120,
            "languages": ["Python"],
            "files": [],
            "has_tests": False,
            "has_readme": False,
            "todo_count": 2,
            "largest_files": [{"path": "app.py", "lines": 90, "size": 2000}],
            "diff": {
                "base": "abc1234",
                "files_changed": 2,
                "insertions": 30,
                "deletions": 5,
                "truncated": False,
                "patch": "",
            },
            "diff_reason": None,
        },
    }
    result = await worker.run(context)
    assert result.posted is True
    assert MARKER in result.body
    assert "app.py" in result.body
    assert "TODO/FIXME" in result.body
    assert "abc1234" in result.body
    assert "```" not in result.body


async def test_mock_provider_without_repo_context() -> None:
    worker = AgentWorker(MockProvider())
    result = await worker.run({})
    assert result.posted is True
    assert "código descargado" in result.body


def test_guardrails_block_code_fence() -> None:
    feedback = AgentFeedback(
        funcionalidad="ok",
        calidad="mira:\n```python\nprint(1)\n```",
        diseno="ok",
        pista=Hint(level=1, text="ok"),
    )
    with pytest.raises(guardrails.GuardrailViolation, match="bloque de código"):
        guardrails.enforce(feedback)


def test_guardrails_block_solution() -> None:
    feedback = AgentFeedback(
        funcionalidad="La solución es esta.",
        calidad="ok",
        diseno="ok",
        pista=Hint(level=1, text="ok"),
    )
    with pytest.raises(guardrails.GuardrailViolation, match="solución"):
        guardrails.enforce(feedback)


def test_guardrails_block_code_line() -> None:
    feedback = AgentFeedback(
        funcionalidad="ok",
        calidad="ok",
        diseno="def suma(a, b):",
        pista=Hint(level=1, text="ok"),
    )
    with pytest.raises(guardrails.GuardrailViolation, match="código"):
        guardrails.enforce(feedback)


def test_unknown_provider_is_rejected() -> None:
    with pytest.raises(ValueError, match="no soportado"):
        build_provider("gpt-9000")
