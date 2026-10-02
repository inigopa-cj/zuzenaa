import json

from zuzenaa.api.analyses import _feedback
from zuzenaa.db.models import Analysis


def _analysis(feedback_json: str) -> Analysis:
    return Analysis(
        repository_id=1,
        commit_sha="a" * 40,
        commit_committed_at=None,
        snapshot_path="/tmp/snap",
        provider="mock",
        feedback_json=feedback_json,
        feedback_md="feedback",
        evolution=None,
        created_at=0,
    )


def test_feedback_parses_structured_payload() -> None:
    payload = {
        "provider": "mock",
        "funcionalidad": "1 fichero",
        "calidad": "ok",
        "diseno": "ok",
        "pista": {"level": 2, "text": "prueba el caso vacío"},
        "teoria": None,
    }
    result = _feedback(_analysis(json.dumps(payload)))
    assert result is not None
    assert result.funcionalidad == "1 fichero"
    assert result.pista.level == 2


def test_feedback_returns_none_for_legacy_payload() -> None:
    assert _feedback(_analysis(json.dumps({"provider": "mock"}))) is None


def test_feedback_returns_none_for_invalid_json() -> None:
    assert _feedback(_analysis("not-json")) is None
