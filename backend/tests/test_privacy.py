"""Privacidad: seudónimos estables y la identidad nunca llega al agente."""

import json
from pathlib import Path
from typing import ClassVar, cast
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from zuzenaa.agent import service as agent_service
from zuzenaa.agent.llm import MockProvider
from zuzenaa.api.analyses import reveal_identity
from zuzenaa.api.repos import list_repos
from zuzenaa.config import settings
from zuzenaa.db.models import IdentityReveal, Repository, User
from zuzenaa.db.session import SessionLocal, init_models
from zuzenaa.github.cli import GhCli
from zuzenaa.github.models import Student
from zuzenaa.privacy import pseudonyms
from zuzenaa.privacy.scrub import leaks, scrub
from zuzenaa.util import now_epoch


def _user(login: str) -> User:
    return User(github_id=1, login=login, encrypted_token="x", created_at=0, updated_at=0)


def _gh(staff: list[str]) -> GhCli:
    fake = AsyncMock(spec=GhCli)
    fake.staff.return_value = [Student(username=login) for login in staff]
    return cast(GhCli, fake)


def test_alias_format() -> None:
    assert pseudonyms.make_alias(3, "Ane", "Urrutia Garmendia") == "3.URGAA"
    # Sin tildes, sin partículas («de la»), Ñ → N.
    assert pseudonyms.make_alias(1, "Íñigo", "Pérez de la Fuente") == "1.PEFUI"
    assert pseudonyms.make_alias(12, "Nerea", "Ibáñez") == "12.IBXXN"  # un solo apellido
    assert pseudonyms.make_alias(4, None, None) == "4.XXXXX"  # sin nombre en el roster


async def test_positions_follow_class_list_and_never_change() -> None:
    await init_models()
    org, room = "priv-o", "priv-c1"
    first = await pseudonyms.ensure_roster(
        org,
        room,
        [
            Student(username="zzz", first_name="Ane", last_name="Urrutia Garmendia"),
            Student(username="aaa", first_name="Jon", last_name="Agirre Lasa"),
            Student(username="sin-nombre"),
        ],
    )
    # Orden de lista: por apellidos (la que no tiene nombre ordena por login, al principio).
    assert first == {"sin-nombre": "1.XXXXX", "aaa": "2.AGLAJ", "zzz": "3.URGAA"}

    # Alguien nuevo va al final; los demás no cambian. El provisional se completa
    # una sola vez manteniendo su posición.
    second = await pseudonyms.ensure_roster(
        org,
        room,
        [
            Student(username="bbb", first_name="Miren", last_name="Arana Etxe"),
            Student(username="sin-nombre", first_name="Leire", last_name="Mendia Arana"),
        ],
    )
    assert second["aaa"] == "2.AGLAJ" and second["zzz"] == "3.URGAA"
    assert second["bbb"] == "4.ARETM"
    assert second["sin-nombre"] == "1.MEARL"
    assert await pseudonyms.resolve(org, room, "3.urgaa") == "zzz"


def test_scrub_replaces_identity_but_not_ordinary_words() -> None:
    terms = ["ane-urrutia", "Ane", "Urrutia", "Garmendia", "Ane Urrutia Garmendia"]
    code = {
        "patch": "# Egilea: ane-urrutia\n# Ane Urrutia Garmendia\nplane = urrutiaz = 1\n",
        "files": [{"path": "ane-urrutia/main.py"}],
    }
    clean = scrub(code, terms, "3.URGAA")
    text = json.dumps(clean)
    assert "ane-urrutia" not in text and "Garmendia" not in text
    assert "3.URGAA" in text
    assert "plane" in text and "urrutiaz" in text  # palabras que solo contienen el nombre
    assert leaks(clean, terms) == []
    assert leaks(code, terms)  # sin limpiar, sí hay fugas


class _Capturing(MockProvider):
    seen: ClassVar[list[str]] = []

    async def generate(self, *, prompt: str, context: dict[str, object]) -> str:
        _Capturing.seen.append(json.dumps(context, ensure_ascii=False))
        return await super().generate(prompt=prompt, context=context)


async def test_agent_never_receives_login_or_name(monkeypatch: pytest.MonkeyPatch) -> None:
    await init_models()
    org, room, login = "priv-o", "priv-c2", "ane-urrutia"
    await pseudonyms.ensure_roster(
        org, room, [Student(username=login, first_name="Ane", last_name="Urrutia Garmendia")]
    )
    local = Path(settings.data_root) / org / room / "a1" / "repos" / login
    local.mkdir(parents=True, exist_ok=True)
    (local / "main.py").write_text(
        "# Egilea: ane-urrutia (Ane Urrutia Garmendia)\nprint('kaixo')\n"
    )
    now = now_epoch()
    async with SessionLocal() as session:
        repo = Repository(
            org=org, classroom=room, assignment="a1", owner=login,
            repo_full_name=f"{room}-a1-{login}", path=str(local), head_sha="c" * 40,
            head_committed_at=now, last_synced_at=now, status="ok",
            created_at=now, updated_at=now,
        )
        session.add(repo)
        await session.commit()
        await session.refresh(repo)

    _Capturing.seen.clear()
    monkeypatch.setattr(agent_service, "get_provider", lambda: _Capturing())
    outcome = await agent_service.analyze_repository(repo)

    assert outcome.status == "analysed"
    [sent] = _Capturing.seen
    for personal in ("ane-urrutia", "Urrutia", "Garmendia", "Ane"):
        assert personal.lower() not in sent.lower(), personal
    assert "1.URGAA" in sent  # en su lugar va el seudónimo


async def test_management_lists_use_pseudonyms_and_reveal_is_staff_only() -> None:
    await init_models()
    org, room = "priv-o", "priv-c3"
    login = "jon-agirre"
    await pseudonyms.ensure_roster(
        org, room, [Student(username=login, first_name="Jon", last_name="Agirre Lasa")]
    )
    now = now_epoch()
    async with SessionLocal() as session:
        session.add(
            Repository(
                org=org, classroom=room, assignment="a1", owner=login,
                repo_full_name=f"{room}-a1-{login}", path="/tmp/none", head_sha=None,
                head_committed_at=None, last_synced_at=now, status="error",
                detail=f"git clone falló: file:///data/o/{room}-a1-{login} not found",
                created_at=now, updated_at=now,
            )
        )
        await session.commit()

    [row] = await list_repos(org, room, "a1", user=_user("tutor"), gh=_gh(["tutor"]))
    assert row.owner == "1.AGLAJ"
    assert login not in row.repo_label
    # Los mensajes de error de git llevan la URL con el login: también se limpian.
    assert row.detail is not None and login not in row.detail and "1.AGLAJ" in row.detail

    with pytest.raises(HTTPException) as exc:
        await reveal_identity(org, room, "a1", "1.AGLAJ", user=_user("alumna"), gh=_gh([]))
    assert exc.value.status_code == 403

    who = await reveal_identity(org, room, "a1", "1.AGLAJ", user=_user("tutor"), gh=_gh(["tutor"]))
    assert (who.login, who.first_name, who.last_name) == (login, "Jon", "Agirre Lasa")
    async with SessionLocal() as session:
        logged = (
            await session.execute(select(IdentityReveal).where(IdentityReveal.classroom == room))
        ).scalars().all()
    assert [(r.alias, r.viewer_login) for r in logged] == [("1.AGLAJ", "tutor")]
