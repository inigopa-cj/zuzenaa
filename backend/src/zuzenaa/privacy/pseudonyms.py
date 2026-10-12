"""Seudónimos del alumnado: ``<posición>.<AP1><AP2><N>`` (p. ej. ``3.URGAA``).

- ``posición``: número en la lista de la clase. Se fija **la primera vez** que el
  alumno aparece (orden alfabético por apellidos y nombre del roster de Classroom 50);
  quien llega después va al final. Así el código no cambia nunca.
- ``AP1``/``AP2``: 2 primeras letras del primer y del segundo apellido; ``N``: inicial
  del nombre. Sin tildes y en mayúsculas; si falta un dato se rellena con ``X``.
- Sin nombre en el roster (solo login), el código queda ``<posición>.XXXXX`` y se
  completa **una sola vez**, manteniendo la posición, cuando llegan los nombres.

El seudónimo es por **clase**: dentro de ella es el mismo en todos los procesos
(tablas, fichas, URLs, análisis y progreso). El login solo se usa dentro del backend
para clonar; el nombre real se guarda cifrado.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass

from sqlalchemy import func, select

from zuzenaa.auth.security import cipher
from zuzenaa.db.models import Pseudonym
from zuzenaa.db.session import SessionLocal
from zuzenaa.github.models import Student
from zuzenaa.util import now_epoch

_PARTICLES = frozenset({"de", "del", "la", "las", "los", "y", "i", "da", "do", "dos", "van", "von"})
_PLACEHOLDER = "XXXXX"


@dataclass
class Identity:
    login: str
    first_name: str | None
    last_name: str | None


def _letters(text: str) -> str:
    """Solo letras A-Z, sin tildes (Ñ → N), en mayúsculas."""
    plain = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Za-z]", "", plain).upper()


def _surnames(last_name: str | None) -> list[str]:
    words = [w for w in (last_name or "").split() if w.lower() not in _PARTICLES]
    return [_letters(w) for w in words if _letters(w)]


def make_alias(position: int, first_name: str | None, last_name: str | None) -> str:
    """``3.URGAA`` para la n.º 3, Ane Urrutia Garmendia."""
    surnames = _surnames(last_name)
    first = _letters(first_name or "")
    if not surnames and not first:
        return f"{position}.{_PLACEHOLDER}"
    ap1 = (surnames[0][:2] if surnames else "").ljust(2, "X")
    ap2 = (surnames[1][:2] if len(surnames) > 1 else "").ljust(2, "X")
    initial = first[:1] or "X"
    return f"{position}.{ap1}{ap2}{initial}"


def _encrypt_name(first: str | None, last: str | None) -> str | None:
    if not (first or last):
        return None
    return cipher.encrypt(f"{first or ''}|{last or ''}")


def _decrypt_name(value: str | None) -> tuple[str | None, str | None]:
    if not value:
        return None, None
    first, _, last = cipher.decrypt(value).partition("|")
    return first or None, last or None


def _sort_key(student: Student) -> tuple[str, str, str]:
    return (
        " ".join(_surnames(student.last_name)),
        _letters(student.first_name or ""),
        student.username.lower(),
    )


async def ensure_roster(org: str, classroom: str, students: Iterable[Student]) -> dict[str, str]:
    """Asigna seudónimo a quien no lo tenga (y completa los provisionales). login → alias."""
    roster = {s.username.lower(): s for s in students}
    now = now_epoch()
    async with SessionLocal() as session:
        rows = (
            await session.execute(
                select(Pseudonym).where(Pseudonym.org == org, Pseudonym.classroom == classroom)
            )
        ).scalars().all()
        by_login = {row.login: row for row in rows}
        next_position = max((row.position for row in rows), default=0) + 1

        # Completar una sola vez los códigos provisionales (misma posición).
        for login, row in by_login.items():
            student = roster.get(login)
            if student and row.alias.endswith(_PLACEHOLDER):
                alias = make_alias(row.position, student.first_name, student.last_name)
                if not alias.endswith(_PLACEHOLDER):
                    row.alias = alias
                    row.encrypted_name = _encrypt_name(student.first_name, student.last_name)
                    row.updated_at = now

        # Nuevos: orden de lista de clase (apellidos, nombre), al final de los existentes.
        for student in sorted(
            (s for login, s in roster.items() if login not in by_login), key=_sort_key
        ):
            row = Pseudonym(
                org=org,
                classroom=classroom,
                login=student.username.lower(),
                position=next_position,
                alias=make_alias(next_position, student.first_name, student.last_name),
                encrypted_name=_encrypt_name(student.first_name, student.last_name),
                created_at=now,
                updated_at=now,
            )
            session.add(row)
            by_login[row.login] = row
            next_position += 1
        await session.commit()
        return {login: row.alias for login, row in by_login.items()}


async def alias_for(org: str, classroom: str, login: str) -> str:
    """Seudónimo de ``login`` (si no está en ningún roster aún, uno provisional)."""
    mapping = await aliases(org, classroom)
    alias = mapping.get(login.lower())
    if alias is not None:
        return alias
    return (await ensure_roster(org, classroom, [Student(username=login)]))[login.lower()]


async def aliases(org: str, classroom: str) -> dict[str, str]:
    """login (minúsculas) → alias de una clase."""
    async with SessionLocal() as session:
        rows = (
            await session.execute(
                select(Pseudonym.login, Pseudonym.alias).where(
                    Pseudonym.org == org, Pseudonym.classroom == classroom
                )
            )
        ).all()
    return {str(login): str(alias) for login, alias in rows}


async def aliases_for_logins(org: str, classroom: str, logins: Iterable[str]) -> dict[str, str]:
    """Como ``aliases`` pero garantizando uno para cada login pedido."""
    wanted = {login.lower() for login in logins}
    mapping = await aliases(org, classroom)
    missing = [Student(username=login) for login in wanted if login not in mapping]
    if missing:
        mapping = await ensure_roster(org, classroom, missing)
    return mapping


async def resolve(org: str, classroom: str, alias: str) -> str | None:
    """alias → login (o ``None`` si no existe en esa clase)."""
    async with SessionLocal() as session:
        return (
            await session.execute(
                select(Pseudonym.login).where(
                    Pseudonym.org == org,
                    Pseudonym.classroom == classroom,
                    func.upper(Pseudonym.alias) == alias.upper(),
                )
            )
        ).scalar_one_or_none()


async def identity(org: str, classroom: str, login: str) -> Identity:
    async with SessionLocal() as session:
        row = (
            await session.execute(
                select(Pseudonym).where(
                    Pseudonym.org == org,
                    Pseudonym.classroom == classroom,
                    Pseudonym.login == login.lower(),
                )
            )
        ).scalar_one_or_none()
    first, last = _decrypt_name(row.encrypted_name if row else None)
    return Identity(login=login, first_name=first, last_name=last)


async def personal_terms(org: str, classroom: str, login: str) -> list[str]:
    """Todo lo que identifica al alumno y no debe llegar al agente."""
    who = await identity(org, classroom, login)
    terms = {login, login.replace("-", " "), login.replace("_", " ")}
    for part in re.split(r"[-_.\s]+", login):
        terms.add(part)
    for value in (who.first_name, who.last_name):
        if value:
            terms.add(value)
            terms.update(value.split())
    if who.first_name and who.last_name:
        terms.add(f"{who.first_name} {who.last_name}")
    # Palabras muy cortas o partículas darían falsos positivos en el código.
    return sorted(
        (t for t in terms if len(t) >= 3 and t.lower() not in _PARTICLES),
        key=len,
        reverse=True,
    )


async def scrub_text(org: str, classroom: str, login: str, text: str | None) -> str | None:
    """Mensajes de error (p. ej. la URL de clonado de git) sin login ni nombre."""
    if not text:
        return text
    from zuzenaa.privacy.scrub import scrub

    alias = await alias_for(org, classroom, login)
    terms = await personal_terms(org, classroom, login)
    return str(scrub(text, terms, alias))


__all__ = [
    "Identity",
    "alias_for",
    "aliases",
    "aliases_for_logins",
    "ensure_roster",
    "identity",
    "make_alias",
    "personal_terms",
    "resolve",
    "scrub_text",
]
