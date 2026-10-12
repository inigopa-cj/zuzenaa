"""Carga los datos de la BD y del clon y calcula el progreso (``metrics.py``).

Se calcula al leer, no se guarda: son operaciones baratas sobre lo que ya existe
(filas ``analyses`` + ``git log`` del clon) y así siempre está al día tras un push o
un «Analizar». Si en el futuro un LLM real redacta los resúmenes, se cacheará el
texto por el último análisis incluido.
"""

from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import select

from zuzenaa.db.models import Analysis, Repository
from zuzenaa.db.session import SessionLocal
from zuzenaa.progress.metrics import (
    AnalysisRecord,
    ClassEvolution,
    StudentProgress,
    class_evolution,
    student_progress,
)
from zuzenaa.repos import git
from zuzenaa.util import now_epoch


def _record(analysis: Analysis) -> AnalysisRecord:
    try:
        payload = json.loads(analysis.feedback_json)
    except json.JSONDecodeError:
        payload = {}
    return AnalysisRecord(
        commit_sha=analysis.commit_sha,
        at=analysis.commit_committed_at or analysis.created_at,
        payload=payload if isinstance(payload, dict) else {},
    )


async def _commits(repo: Repository) -> list[git.CommitInfo]:
    path = Path(repo.path)
    if repo.status != "ok" or not (path / ".git").is_dir():
        return []
    try:
        return await git.log(path)
    except git.GitError:
        return []


async def progress_for(repo: Repository, *, now: int | None = None) -> StudentProgress:
    async with SessionLocal() as session:
        stmt = (
            select(Analysis)
            .where(Analysis.repository_id == repo.id)
            .order_by(Analysis.created_at)
        )
        analyses = (await session.execute(stmt)).scalars().all()
    return student_progress(
        repo.owner,
        [_record(a) for a in analyses],
        await _commits(repo),
        now=now if now is not None else now_epoch(),
    )


async def repositories(
    org: str, classroom: str, assignment: str, owner: str | None = None
) -> list[Repository]:
    async with SessionLocal() as session:
        stmt = select(Repository).where(
            Repository.org == org,
            Repository.classroom == classroom,
            Repository.assignment == assignment,
        )
        if owner is not None:
            stmt = stmt.where(Repository.owner == owner)
        return list((await session.execute(stmt.order_by(Repository.owner))).scalars().all())


async def class_progress(
    org: str, classroom: str, assignment: str, *, now: int | None = None
) -> ClassEvolution:
    """Evolución de la clase: agrega el progreso de cada entrega descargada."""
    stamp = now if now is not None else now_epoch()
    repos = [r for r in await repositories(org, classroom, assignment) if r.status == "ok"]
    return class_evolution([await progress_for(repo, now=stamp) for repo in repos])


__all__ = ["class_progress", "progress_for", "repositories"]
