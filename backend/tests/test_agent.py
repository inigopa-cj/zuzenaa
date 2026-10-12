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


def _tests_payload(passing: dict[str, bool]) -> dict[str, object]:
    cases: list[dict[str, object]] = [
        {"name": name, "passed": ok, "points": 5 if ok else 0, "max_points": 5}
        for name, ok in passing.items()
    ]
    return {
        "commit": "b" * 40,
        "score": 5 * sum(passing.values()),
        "max_score": 5 * len(cases),
        "tests": cases,
        "passed": sum(1 for ok in passing.values() if ok),
        "total": len(cases),
    }


async def test_mock_provider_comments_failing_tests() -> None:
    worker = AgentWorker(MockProvider())
    context: dict[str, object] = {
        "repo": {"file_count": 1, "line_count": 10, "languages": ["Python"]},
        "tests": _tests_payload({"test_batu": True, "test_sarrera_okerra": False}),
        "previous_tests": _tests_payload({"test_batu": False, "test_sarrera_okerra": False}),
    }
    result = await worker.run(context)
    assert result.posted is True
    assert result.feedback is not None
    assert "pasan 1 de 2 (5/10 puntos)" in result.feedback.funcionalidad
    assert "Mejora" in result.feedback.funcionalidad
    assert "test_sarrera_okerra" in result.feedback.pista.text


async def test_mock_provider_warns_on_regression_and_all_green() -> None:
    worker = AgentWorker(MockProvider())
    regression = await worker.run(
        {
            "repo": {"file_count": 1},
            "tests": _tests_payload({"a": False}),
            "previous_tests": _tests_payload({"a": True}),
        }
    )
    assert regression.feedback is not None
    assert "algo se ha roto" in regression.feedback.funcionalidad

    green = await worker.run({"repo": {"file_count": 1}, "tests": _tests_payload({"a": True})})
    assert green.feedback is not None
    assert "Falla" not in green.feedback.funcionalidad
    assert "pasan" in green.feedback.pista.text


async def test_mock_hint_points_at_what_is_missing() -> None:
    worker = AgentWorker(MockProvider())
    todo = await worker.run({"repo": {"todo_count": 2, "has_tests": True, "has_readme": True}})
    no_tests = await worker.run({"repo": {"has_tests": False, "has_readme": True}})
    done = await worker.run({"repo": {"has_tests": True, "has_readme": True}})
    assert todo.feedback is not None and "TODO" in todo.feedback.pista.text
    assert no_tests.feedback is not None and "caso de prueba" in no_tests.feedback.pista.text
    assert done.feedback is not None and "entrada vacía" in done.feedback.pista.text
