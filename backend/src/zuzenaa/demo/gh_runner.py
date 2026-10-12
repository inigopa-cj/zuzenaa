"""Runner in-process que emula ``gh`` / ``gh teacher`` con el dataset demo.

Se inyecta en ``GhCli(runner=...)`` cuando ``ZUZENAA_DEMO_MODE=true``; el adaptador
``github/cli.py`` no nota la diferencia: recibe el mismo JSON por stdout (y el
resumen humano por stderr) que daría el CLI real. Solo se emulan los comandos que
usa ZuzenAA; cualquier otro falla con código 1, como haría ``gh`` sin red.

El staff de la clase es el ficticio del dataset **más** los logins de la tabla
``users`` (salvo los alumnos del dataset), leídos en cada petición: así quien inicie
sesión puede ver la ficha de cualquier alumno de la demo sin volver a sembrar, y
quien entre como un alumno ficticio ve la superficie del alumno.
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable, Mapping, Sequence

from sqlalchemy import select

from zuzenaa.db.models import User
from zuzenaa.db.session import SessionLocal
from zuzenaa.demo import dataset
from zuzenaa.demo.dataset import DemoState
from zuzenaa.github.cli import Runner

StaffProvider = Callable[[], Awaitable[Sequence[str]]]

_STAFF_ROLES = ("instructor", "teacher", "hta", "ta")
_ROSTER_FILES = ("roster.csv", "students.csv")


async def db_staff_logins() -> list[str]:
    """Logins de ``users``: en la demo, quien haya iniciado sesión es staff."""
    async with SessionLocal() as session:
        rows = (await session.execute(select(User.login).order_by(User.login))).scalars().all()
    return list(rows)


def make_demo_runner(
    state: DemoState | None = None, *, staff_provider: StaffProvider | None = None
) -> Runner:
    """Construye el runner. ``staff_provider`` se inyecta en tests (sin BD)."""
    demo = state or dataset.default_state()
    provider = staff_provider or db_staff_logins

    async def run(args: Sequence[str], env: Mapping[str, str]) -> tuple[int, str, str]:
        # args[0] es el binario (``gh``); el token del entorno no hace falta para nada.
        return await _dispatch(demo, provider, list(args)[1:])

    return run


def _ok(payload: object, summary: str = "") -> tuple[int, str, str]:
    return 0, json.dumps(payload), summary


def _not_found() -> tuple[int, str, str]:
    return 1, "", "gh: Not Found (HTTP 404)"


def _not_initialized(org: str) -> tuple[int, str, str]:
    # El mensaje contiene "not found" e "init": la web lo traduce a
    # «Esta organización aún no está preparada en Classroom 50».
    return 1, "", f"{org}/classroom50 not found: run `gh teacher init {org}` first"


async def _dispatch(
    demo: DemoState, provider: StaffProvider, args: list[str]
) -> tuple[int, str, str]:
    if len(args) >= 2 and args[0] == "api":
        return await _api(demo, provider, args[1])
    if len(args) >= 4 and args[:3] == ["teacher", "classroom", "list"]:
        return _classrooms(demo, org=args[3], include_archived="--all" in args)
    if len(args) >= 5 and args[:3] == ["teacher", "assignment", "list"]:
        return _assignments(demo, org=args[3], classroom=args[4])
    return 1, "", f"comando no soportado por el runner demo: gh {' '.join(args)}"


def _classrooms(demo: DemoState, *, org: str, include_archived: bool) -> tuple[int, str, str]:
    if org != demo.org:
        return _not_initialized(org)
    rooms = [room for room in demo.classrooms if include_archived or room["active"]]
    return _ok(rooms, f"{org}/classroom50: {len(rooms)} classroom(s)")


def _assignments(demo: DemoState, *, org: str, classroom: str) -> tuple[int, str, str]:
    if org != demo.org:
        return _not_initialized(org)
    if classroom not in demo.assignments:
        return 1, "", f"classroom {classroom!r} not found in {org}/classroom50"
    items = list(demo.assignments[classroom])
    return _ok(items, f"{org}/classroom50/{classroom}: {len(items)} assignment(s)")


async def _api(demo: DemoState, provider: StaffProvider, endpoint: str) -> tuple[int, str, str]:
    parts = endpoint.split("?", 1)[0].strip("/").split("/")
    if parts == ["user", "orgs"]:
        return _ok(
            [
                {
                    "login": demo.org,
                    "description": dataset.DEMO_ORG_DESCRIPTION,
                    "avatar_url": None,
                }
            ]
        )
    if len(parts) == 3 and parts[0] == "orgs" and parts[2] == "repos":
        # Plantillas de la org: la web no las usa; una lista vacía es válida.
        return _ok([]) if parts[1] == demo.org else _not_found()
    if len(parts) == 5 and parts[0] == "orgs" and parts[2:5:2] == ["teams", "members"]:
        return await _members(demo, provider, org=parts[1], slug=parts[3])
    if len(parts) == 6 and parts[0] == "repos" and parts[2:4] == ["classroom50", "contents"]:
        return _roster_file(demo, org=parts[1], classroom=parts[4], filename=parts[5])
    return _not_found()


async def _members(
    demo: DemoState, provider: StaffProvider, *, org: str, slug: str
) -> tuple[int, str, str]:
    if org != demo.org:
        return _not_found()
    for room in demo.classrooms:
        base = room["team"]["slug"]
        if slug == base:
            students = dataset.students_of(demo, room["short_name"])
            return _ok([{"login": student["username"]} for student in students])
        for role in _STAFF_ROLES:
            if slug != f"{base}-{role}":
                continue
            logins = [member["username"] for member in demo.staff if member["role"] == role]
            if role == "instructor":
                # Quien inicia sesión es staff, salvo los alumnos del dataset: así se
                # puede probar la superficie del alumno entrando como uno de ellos.
                dataset_students = {student["username"] for student in demo.students}
                logins.extend(
                    login
                    for login in await provider()
                    if login not in logins and login not in dataset_students
                )
            return _ok([{"login": login} for login in logins])
    return _not_found()


def _roster_file(
    demo: DemoState, *, org: str, classroom: str, filename: str
) -> tuple[int, str, str]:
    known = {room["short_name"] for room in demo.classrooms}
    if org != demo.org or classroom not in known or filename not in _ROSTER_FILES:
        return _not_found()
    if filename != "roster.csv":
        return _not_found()  # en la demo solo existe roster.csv
    return 0, dataset.roster_csv(demo, classroom), ""


__all__ = ["StaffProvider", "db_staff_logins", "make_demo_runner"]
