from typing import cast
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from zuzenaa.api.analyses import _authorize_owner
from zuzenaa.api.me import my_assignments
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

    result = await my_assignments(_user("octocat"))
    assert {item.owner for item in result} == {"octocat"}
    assert result[0].analyses == 1


def test_my_assignments_requires_session() -> None:
    with TestClient(app) as client:
        assert client.get("/me/assignments").status_code == 401
