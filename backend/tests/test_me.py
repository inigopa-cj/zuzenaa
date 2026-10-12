from typing import cast
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from zuzenaa.api.analyses import _authorize_owner
from zuzenaa.api.me import my_assignments, my_role
from zuzenaa.api.repos import list_repos
from zuzenaa.auth import roles
from zuzenaa.config import settings
from zuzenaa.db.models import Analysis, Repository, User
from zuzenaa.db.session import SessionLocal, init_models
from zuzenaa.github.cli import GhCli
from zuzenaa.github.models import Student
from zuzenaa.main import app
from zuzenaa.util import now_epoch


def _user(login: str) -> User:
    return User(github_id=1, login=login, encrypted_token="x", created_at=0, updated_at=0)


def _gh(staff: list[str]) -> GhCli:
    fake = AsyncMock(spec=GhCli)
    fake.staff.return_value = [Student(username=login) for login in staff]
    return cast(GhCli, fake)


async def test_authorize_owner_allows_self() -> None:
    await _authorize_owner(
        org="o", classroom="c", owner="octocat", user=_user("octocat"), gh=_gh([])
    )


async def test_authorize_owner_allows_staff() -> None:
    await _authorize_owner(
        org="o", classroom="c", owner="ana", user=_user("teacher"), gh=_gh(["teacher"])
    )


async def test_authorize_owner_denies_other_student() -> None:
    with pytest.raises(HTTPException) as exc:
        await _authorize_owner(
            org="o", classroom="c", owner="ana", user=_user("bob"), gh=_gh([])
        )
    assert exc.value.status_code == 403


async def test_authorize_owner_requires_session(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "allow_env_token", False)
    with pytest.raises(HTTPException) as exc:
        await _authorize_owner(org="o", classroom="c", owner="ana", user=None, gh=_gh([]))
    assert exc.value.status_code == 401


async def test_my_assignments_filters_by_login() -> None:
    await init_models()
    now = now_epoch()
    async with SessionLocal() as session:
        repo = Repository(
            org="o", classroom="c1", assignment="a1", owner="octocat",
            repo_full_name="c1-a1-octocat", path="/tmp/none", head_sha="a" * 40,
            head_committed_at=now, last_synced_at=now, status="ok",
            created_at=now, updated_at=now,
        )
        other = Repository(
            org="o", classroom="c1", assignment="a1", owner="someone",
            repo_full_name="c1-a1-someone", path="/tmp/none2", head_sha="b" * 40,
            head_committed_at=now, last_synced_at=now, status="ok",
            created_at=now, updated_at=now,
        )
        session.add_all([repo, other])
        await session.commit()
        await session.refresh(repo)
        session.add(
            Analysis(
                repository_id=repo.id, commit_sha="a" * 40, commit_committed_at=now,
                snapshot_path="/tmp/s", provider="mock", feedback_json="{}",
                feedback_md="x", evolution=None, created_at=now, forced=False,
            )
        )
        await session.commit()

    result = await my_assignments(_user("octocat"), _gh([]))
    assert {item.owner for item in result} == {"octocat"}
    assert result[0].analyses == 1


def test_my_assignments_requires_session() -> None:
    with TestClient(app) as client:
        assert client.get("/me/assignments").status_code == 401



async def _repo(org: str, classroom: str, owner: str) -> None:
    now = now_epoch()
    async with SessionLocal() as session:
        session.add(
            Repository(
                org=org, classroom=classroom, assignment="a1", owner=owner,
                repo_full_name=f"{classroom}-a1-{owner}", path=f"/tmp/{owner}",
                head_sha=None, head_committed_at=None, last_synced_at=now, status="ok",
                created_at=now, updated_at=now,
            )
        )
        await session.commit()


async def test_role_staff_student_and_unknown() -> None:
    await init_models()
    await _repo("ro", "rc", "alumna")
    roles.clear_cache()

    staff = await my_role(_user("irakasle"), _gh(["irakasle"]))
    assert staff.role == "staff"
    assert {(r.org, r.classroom) for r in staff.staff_of} >= {("ro", "rc")}

    student = await my_role(_user("alumna"), _gh(["irakasle"]))
    assert (student.role, student.owns_repos) == ("student", True)

    nobody = await my_role(_user("nadie"), _gh(["irakasle"]))
    assert nobody.role == "unknown"


async def test_staff_can_preview_a_student_but_students_cannot() -> None:
    await init_models()
    await _repo("po", "pc", "preview-alumna")
    await _repo("other-org", "oc", "preview-alumna")
    roles.clear_cache()

    async def staff_only_in_pc(org: str, classroom: str) -> list[Student]:
        return [Student(username="tutor")] if (org, classroom) == ("po", "pc") else []

    gh = _gh([])
    cast(AsyncMock, gh.staff).side_effect = staff_only_in_pc
    seen = await my_assignments(_user("tutor"), gh, as_login="preview-alumna")
    # Solo las clases donde quien mira es staff.
    assert {(i.org, i.classroom) for i in seen} == {("po", "pc")}

    roles.clear_cache()
    with pytest.raises(HTTPException) as exc:
        await my_assignments(_user("otra-alumna"), _gh([]), as_login="preview-alumna")
    assert exc.value.status_code == 403


async def test_management_endpoints_are_staff_only() -> None:
    with pytest.raises(HTTPException) as exc:
        await list_repos("o", "c", "a", user=_user("alumna"), gh=_gh([]))
    assert exc.value.status_code == 403
    assert await list_repos("o", "c", "a", user=_user("tutor"), gh=_gh(["tutor"])) == []
