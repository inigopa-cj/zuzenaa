"""Modo demo: dataset, runner que emula ``gh``, siembra y push simulado end-to-end."""

import json
from datetime import date
from itertools import pairwise

import pytest
from sqlalchemy import delete, select

from zuzenaa.config import settings
from zuzenaa.db.models import Analysis, Repository, User
from zuzenaa.db.session import SessionLocal, init_models
from zuzenaa.demo import dataset, gh_runner, origins_root, push, releases, seed
from zuzenaa.github.cli import GhCli, GhError
from zuzenaa.repos import paths

_TODAY = date(2026, 3, 10)


def _cli(staff: list[str] | None = None) -> GhCli:
    async def provider() -> list[str]:
        return staff or []

    return GhCli(token="demo", runner=gh_runner.make_demo_runner(staff_provider=provider))


async def test_runner_emulates_orgs_and_classrooms() -> None:
    cli = _cli()
    orgs = await cli.orgs()
    assert [org.login for org in orgs] == [dataset.DEMO_ORG]

    rooms = await cli.classrooms(dataset.DEMO_ORG)
    assert [room.short_name for room in rooms] == [dataset.ACTIVE_CLASSROOM]

    all_rooms = await cli.classrooms(dataset.DEMO_ORG, include_archived=True)
    assert {room.short_name for room in all_rooms} == {
        dataset.ACTIVE_CLASSROOM,
        dataset.ARCHIVED_CLASSROOM,
    }


async def test_runner_emulates_assignments_and_templates() -> None:
    cli = _cli()
    assignments = await cli.assignments(dataset.DEMO_ORG, dataset.ACTIVE_CLASSROOM)
    assert [item.slug for item in assignments] == [dataset.ASSIGNMENT_P1, dataset.ASSIGNMENT_P2]
    assert assignments[0].template is not None
    assert assignments[0].template.repo == dataset.TEMPLATE_REPO
    assert await cli.templates(dataset.DEMO_ORG) == []


async def test_runner_roster_merges_team_and_csv() -> None:
    cli = _cli()
    students = await cli.roster(dataset.DEMO_ORG, dataset.ACTIVE_CLASSROOM)
    assert [student.username for student in students] == sorted(
        student["username"] for student in dataset.STUDENTS
    )
    ane = next(student for student in students if student.username == "ane-urrutia")
    assert ane.first_name == "Ane"
    assert ane.email == "ane.urrutia@ikastola-demo.test"


async def test_runner_staff_includes_injected_logins() -> None:
    cli = _cli(staff=["irakasle-mikel"])
    staff = await cli.staff(dataset.DEMO_ORG, dataset.ACTIVE_CLASSROOM)
    logins = {member.username for member in staff}
    assert {"irakasle-miren", "praktikante-urtzi", "irakasle-mikel"} <= logins


async def test_runner_unknown_org_reports_not_initialized() -> None:
    cli = _cli()
    assert await cli.orgs()  # el runner responde a la org conocida
    with pytest.raises(GhError, match="not found"):
        await cli.classrooms("otra-org")


async def test_runner_unknown_command_fails_like_gh() -> None:
    cli = _cli()
    with pytest.raises(GhError):
        await cli.templates("otra-org")


def test_dataset_offsets_are_strictly_decreasing() -> None:
    for assignment, per_owner in dataset.SUBMISSIONS.items():
        for owner, spec in per_owner.items():
            offsets = spec.day_offsets
            assert len(offsets) == spec.commit_count, f"{assignment}/{owner}"
            assert all(a > b for a, b in pairwise(offsets)), f"{assignment}/{owner}"
            assert spec.analyze_count <= spec.commit_count
            assert spec.commit_count <= len(dataset.TRACKS[assignment])


def test_roster_csv_has_expected_columns() -> None:
    state = dataset.default_state(_TODAY)
    header = dataset.roster_csv(state, dataset.ACTIVE_CLASSROOM).splitlines()[0]
    assert header == "username,first_name,last_name,email,section,github_id"


async def test_seed_builds_origins_clones_and_dated_analyses() -> None:
    await init_models()
    async with SessionLocal() as session:
        await session.execute(delete(User))
        await session.commit()

    summary = await seed.seed(today=_TODAY)

    students = [student["username"] for student in dataset.STUDENTS]
    assert summary.origins == 11  # 6 alumnos en p1 + 5 en p2
    assert summary.repos == 11
    assert summary.errors == 1  # Maialen no aceptó la entrega de p2
    assert summary.analyses == 19  # 12 en p1 + 7 en p2

    async with SessionLocal() as session:
        rows = (await session.execute(select(Repository))).scalars().all()
        by_key = {(row.assignment, row.owner): row for row in rows}

        # La entrega no aceptada queda como error, sin HEAD.
        failed = by_key[(dataset.ASSIGNMENT_P2, "maialen-ortiz")]
        assert failed.status == "error"
        assert failed.head_sha is None

        # Jone entregó p1 pero no se analizó: HEAD en el último commit, sin análisis.
        jone = by_key[(dataset.ASSIGNMENT_P1, "jone-larrea")]
        assert jone.status == "ok"
        assert jone.head_sha is not None
        jone_analyses = (
            await session.execute(select(Analysis).where(Analysis.repository_id == jone.id))
        ).scalars().all()
        assert jone_analyses == []

        # Ane tiene 3 análisis en p1, fechados en el commit de cada revisión.
        ane = by_key[(dataset.ASSIGNMENT_P1, "ane-urrutia")]
        analyses = (
            await session.execute(
                select(Analysis)
                .where(Analysis.repository_id == ane.id)
                .order_by(Analysis.created_at)
            )
        ).scalars().all()
        assert len(analyses) == 3
        assert [a.created_at for a in analyses] == sorted(a.created_at for a in analyses)
        assert ane.head_committed_at is not None
        assert all(a.created_at < ane.head_committed_at for a in analyses)
        assert all(a.snapshot_path for a in analyses)

    # Los orígenes git locales existen y son clones válidos.
    for owner in students:
        origin = origins_root() / dataset.DEMO_ORG / paths.repo_full_name(
            dataset.DEMO_ORG, dataset.ACTIVE_CLASSROOM, dataset.ASSIGNMENT_P1, owner
        )
        assert (origin / ".git").is_dir()

def test_track_results_are_aligned_with_tracks() -> None:
    for assignment, track in dataset.TRACKS.items():
        assert len(dataset.TRACK_PASSING[assignment]) == len(track)
        names = {test["name"] for test in dataset.TESTS[assignment]}
        for passing in dataset.TRACK_PASSING[assignment]:
            assert passing <= names
        last = dataset.commit_results(assignment, len(track) - 1, "c" * 40)
        assert last.score == last.max_score  # la última revisión del track pasa todo


async def test_push_commits_publishes_tests_downloads_and_analyses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "demo_mode", True)
    await init_models()
    async with SessionLocal() as session:
        await session.execute(delete(User))
        await session.commit()
    await seed.seed(today=_TODAY)

    full_name = paths.repo_full_name(
        dataset.DEMO_ORG, dataset.ACTIVE_CLASSROOM, dataset.ASSIGNMENT_P1, "jone-larrea"
    )
    # El seed publica la release de cada commit: Jone tiene 2 (c1 falla un test).
    origin = origins_root() / dataset.DEMO_ORG / full_name
    first = releases.read(dataset.DEMO_ORG, full_name, seed.commit_shas(origin)[0])
    assert first is not None
    assert first.failing == ["test_sarrera_okerra"]

    # Push de la 3.ª revisión: se descarga y se analiza sin pulsar «Analizar».
    outcome = await push.simulate_push(assignment=dataset.ASSIGNMENT_P1, owner="jone-larrea")
    assert outcome.analysis.status == "analysed"
    assert outcome.analysis.commit_sha == outcome.commit_sha
    assert outcome.tests.passed == 2
    assert outcome.tests.score == outcome.tests.max_score

    async with SessionLocal() as session:
        repo = (
            await session.execute(
                select(Repository).where(
                    Repository.assignment == dataset.ASSIGNMENT_P1,
                    Repository.owner == "jone-larrea",
                )
            )
        ).scalar_one()
        assert repo.head_sha == outcome.commit_sha  # el sync mueve el clon al nuevo push
        analysis = await session.get(Analysis, outcome.analysis.analysis_id)
    assert analysis is not None
    stored = json.loads(analysis.feedback_json)
    assert stored["tests"]["passed"] == 2
    assert "pasan 2 de 2" in stored["funcionalidad"]

    # Último commit del track (c4) y después ya no quedan revisiones por subir.
    await push.simulate_push(assignment=dataset.ASSIGNMENT_P1, owner="jone-larrea")
    with pytest.raises(push.PushError, match="todas las revisiones"):
        await push.simulate_push(assignment=dataset.ASSIGNMENT_P1, owner="jone-larrea")

    # Maialen no aceptó p2: no hay repo al que hacer push.
    with pytest.raises(push.PushError, match="no aceptó"):
        await push.simulate_push(assignment=dataset.ASSIGNMENT_P2, owner="maialen-ortiz")


async def test_runner_dataset_students_are_never_staff() -> None:
    cli = _cli(staff=["irakasle-mikel", "ane-urrutia"])
    members = await cli.staff(dataset.DEMO_ORG, dataset.ACTIVE_CLASSROOM)
    staff = {member.username for member in members}
    assert "irakasle-mikel" in staff
    assert "ane-urrutia" not in staff
