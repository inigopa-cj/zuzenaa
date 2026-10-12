"""Progreso del alumno y evolución de la clase."""

import subprocess
from pathlib import Path

import pytest

from zuzenaa.agent import service as agent_service
from zuzenaa.config import settings
from zuzenaa.db.session import init_models
from zuzenaa.demo import releases
from zuzenaa.github.results import TestCaseResult, TestResults
from zuzenaa.progress import metrics, service
from zuzenaa.repos.git import CommitInfo

DAY = metrics.DAY
NOW = 1_800_000_000


def _record(
    sha: str, day: int, passing: dict[str, bool], hint: str = "pista"
) -> metrics.AnalysisRecord:
    cases = [{"name": n, "passed": ok} for n, ok in passing.items()]
    return metrics.AnalysisRecord(
        commit_sha=sha,
        at=NOW - day * DAY,
        payload={
            "pista": {"level": 2, "text": hint},
            "tests": {
                "tests": cases,
                "score": 5 * sum(passing.values()),
                "max_score": 5 * len(passing),
            },
        },
    )


def _commit(sha: str, day: int, lines: int) -> CommitInfo:
    return CommitInfo(sha, NOW - day * DAY, 1, lines, 0)


def test_student_progress_tracks_tests_regressions_and_hints() -> None:
    records = [
        _record("a" * 40, 10, {"t1": False, "t2": False}, "mira t1"),
        _record("b" * 40, 8, {"t1": True, "t2": False}, "mira t2"),
        _record("c" * 40, 6, {"t1": False, "t2": True}, "mira t1"),
        _record("d" * 40, 5, {"t1": False, "t2": True}, "mira t1"),
        _record("e" * 40, 4, {"t1": False, "t2": True}, "mira t1"),
    ]
    commits = [_commit(r.commit_sha, (NOW - r.at) // DAY, 10) for r in records]
    commits.insert(1, _commit("f" * 40, 9, 400))  # commit grande sin analizar

    p = metrics.student_progress("ane", records, commits, now=NOW)

    assert p.analyses == 5
    assert p.current is not None and (p.current.passed, p.current.total) == (1, 2)
    assert [(r.test, r.commit[0]) for r in p.regressions] == [("t1", "c")]
    t1 = next(t for t in p.tests if t.name == "t1")
    assert (t1.passing, t1.first_passed_commit, t1.regressions) == (False, "b" * 40, 1)
    assert p.hint_streak == 3 and p.repeated_hint == "mira t1"
    assert p.rhythm is not None
    assert (p.rhythm.commits, p.rhythm.analysed_commits, p.rhythm.days_since_last) == (6, 5, 4)
    assert {a.kind for a in p.alerts} == {"pista_repetida"}
    assert "dejó de pasar t1" in p.summary
    assert "commit mucho más grande" in p.summary


def test_student_progress_reanalysis_counts_once_and_flags_stale() -> None:
    records = [
        _record("a" * 40, 20, {"t1": False}),
        _record("a" * 40, 20, {"t1": False}),  # reanálisis del mismo commit
    ]
    p = metrics.student_progress("unai", records, [_commit("a" * 40, 20, 5)], now=NOW)
    assert p.analyses == 1
    assert [a.kind for a in p.alerts] == ["sin_avance"]


def test_student_progress_without_analyses() -> None:
    p = metrics.student_progress("jone", [], [], now=NOW)
    assert p.current is None
    assert [a.kind for a in p.alerts] == ["sin_analisis"]
    assert "Todavía no hay revisiones" in p.summary


def test_class_evolution_aggregates_students() -> None:
    green = metrics.student_progress(
        "ane", [_record("a" * 40, 3, {"t1": True, "t2": True})], [], now=NOW
    )
    half = metrics.student_progress(
        "unai",
        [
            _record("b" * 40, 5, {"t1": False, "t2": False}, "mira t2"),
            _record("c" * 40, 2, {"t1": True, "t2": False}, "mira t2"),
        ],
        [],
        now=NOW,
    )
    empty = metrics.student_progress("jone", [], [], now=NOW)
    half_again = metrics.student_progress(
        "nerea", [_record("d" * 40, 1, {"t1": True, "t2": False}, "mira t2")], [], now=NOW
    )

    c = metrics.class_evolution([green, half, empty, half_again])

    assert (c.students, c.analysed, c.with_tests, c.all_passing) == (4, 3, 3, 1)
    assert [t.name for t in c.tests] == ["t2", "t1"]  # el que más cuesta, primero
    assert (c.tests[0].passing, c.tests[0].students) == (1, 3)
    assert [row.owner for row in c.attention] == ["jone"]
    assert [(h.text, h.students) for h in c.common_hints] == [("mira t2", 2)]
    # La serie diaria usa el último resultado conocido de cada alumno hasta ese día.
    assert c.timeline[0].avg_ratio == 0.0 and c.timeline[0].students == 1
    assert c.timeline[-1].students == 3
    assert "El test que más cuesta es t2" in c.summary


def _git(cwd: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True)
    return result.stdout.strip()


async def test_progress_service_reads_db_and_git_log(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "demo_mode", True)  # lee las releases ficticias
    await init_models()
    org, classroom, assignment, owner = "org", "c3", "a3", "iker"
    full_name = f"{classroom}-{assignment}-{owner}"
    origin = tmp_path / org / full_name
    origin.mkdir(parents=True)
    _git(origin, "init", "-q", "-b", "main")

    async def push(content: str, passing: bool) -> None:
        (origin / "main.py").write_text(content)
        _git(origin, "add", "-A")
        _git(origin, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "c")
        sha = _git(origin, "rev-parse", "HEAD")
        case = TestCaseResult("test_main", passing, 10 if passing else 0, 10)
        releases.write(org, full_name, TestResults(sha, case.points, 10, [case]))
        await agent_service.sync_and_analyze(
            org=org,
            classroom=classroom,
            assignment=assignment,
            owners=[owner],
            token="",
            clone_url_template=tmp_path.as_uri() + "/{org}/{repo}",
        )

    await push("print(1)\n", passing=False)
    await push("print(2)\n", passing=True)

    [repo] = await service.repositories(org, classroom, assignment, owner)
    progress = await service.progress_for(repo)
    assert progress.analyses == 2
    assert [pt.passed for pt in progress.timeline] == [0, 1]
    assert progress.rhythm is not None and progress.rhythm.commits == 2

    evolution = await service.class_progress(org, classroom, assignment)
    assert (evolution.students, evolution.all_passing) == (1, 1)


def test_repeated_hint_is_not_an_alert_when_all_tests_pass() -> None:
    records = [_record(c * 40, 9 - i, {"t1": True}, "igual") for i, c in enumerate("abc")]
    p = metrics.student_progress("ane", records, [], now=NOW)
    assert p.hint_streak == 3
    assert p.repeated_hint is None
    assert p.alerts == []
