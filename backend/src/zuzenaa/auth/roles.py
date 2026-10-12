"""Rol de quien inicia sesión: profesorado (staff) o alumnado.

Classroom 50 es la autoridad: alguien es **staff** si aparece en el staff
(``gh teacher``: equipos ``-instructor``/``-ta``...) de alguna clase que ZuzenAA
conoce (las que tienen repos descargados). Si no, y tiene entregas propias, es
**alumno**. Sin datos en ninguno de los dos sentidos el rol es ``unknown`` (p. ej.
un profesor que aún no ha descargado nada); la web lo trata como profesorado,
pero los permisos los sigue decidiendo el backend en cada endpoint.

Se cachea por login unos minutos: evita una llamada a ``gh`` por clase en cada
carga de página.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from sqlalchemy import func, select

from zuzenaa.db.models import Repository
from zuzenaa.db.session import SessionLocal
from zuzenaa.github.cli import GhCli, GhError

_TTL_SECONDS = 300


@dataclass
class ClassroomRef:
    org: str
    classroom: str


@dataclass
class RoleInfo:
    login: str
    role: str  # staff | student | unknown
    staff_of: list[ClassroomRef] = field(default_factory=list)
    owns_repos: bool = False

    def is_staff_of(self, org: str, classroom: str) -> bool:
        return any(ref.org == org and ref.classroom == classroom for ref in self.staff_of)


_cache: dict[str, tuple[float, RoleInfo]] = {}


def clear_cache() -> None:
    _cache.clear()


async def resolve_role(login: str, gh: GhCli) -> RoleInfo:
    key = login.lower()
    cached = _cache.get(key)
    if cached is not None and cached[0] > time.monotonic():
        return cached[1]

    async with SessionLocal() as session:
        pairs = (
            await session.execute(
                select(Repository.org, Repository.classroom)
                .distinct()
                .order_by(Repository.org, Repository.classroom)
            )
        ).all()
        owns = (
            await session.execute(
                select(func.count(Repository.id)).where(func.lower(Repository.owner) == key)
            )
        ).scalar_one()

    staff_of: list[ClassroomRef] = []
    for org, classroom in pairs:
        try:
            staff = await gh.staff(org, classroom)
        except GhError:
            continue  # sin acceso a la configuración de esa clase: no es staff
        if any(member.username.lower() == key for member in staff):
            staff_of.append(ClassroomRef(org, classroom))

    if staff_of:
        role = "staff"
    elif owns:
        role = "student"
    else:
        role = "unknown"
    info = RoleInfo(login=login, role=role, staff_of=staff_of, owns_repos=bool(owns))
    _cache[key] = (time.monotonic() + _TTL_SECONDS, info)
    return info


__all__ = ["ClassroomRef", "RoleInfo", "clear_cache", "resolve_role"]
