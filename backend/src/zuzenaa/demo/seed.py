"""Siembra el modo demo: fabrica «GitHub» en local y deja el histórico listo.

Ejecuta ``python -m zuzenaa.demo.seed`` (dentro del contenedor del backend) para:

1. Crear **repos git locales** en ``<DATA_ROOT>/demo-origins/<org>/<repo>`` a partir
   de los *tracks* de commits del dataset. Hacen de GitHub ficticio: el clonado real
   los usa vía ``file://`` (``ZUZENAA_GIT_CLONE_URL_TEMPLATE``).
2. **Descargar** (clonar) cada entrega con el mismo código que producción
   (``repos.service.sync_assignment``), incluida la entrega no aceptada de Maialen,
   que queda como fila ``error``.
   Por cada commit escribe también su **release ficticia** con el ``result.json`` de
   los tests (``demo/releases.py``), como haría GitHub Actions en Classroom 50.
3. **Analizar** las revisiones ya entregadas con el agente real, fechando cada
   análisis en la fecha de su commit (``created_at``) para que el histórico y el
   progreso se ordenen como en la vida real. Las revisiones restantes quedan
   pendientes para pulsar «Analizar» en vivo.

Es idempotente: volver a ejecutarlo reconstruye los orígenes y reutiliza los
análisis ya existentes (mismo commit => ``cached``).
"""

from __future__ import annotations

import argparse
import asyncio
import os
import shutil
import stat
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path

from sqlalchemy import select

from zuzenaa.agent import service as agent_service
from zuzenaa.db.models import Repository, User
from zuzenaa.db.session import SessionLocal, init_models
from zuzenaa.demo import clone_url_template, dataset, origins_root, releases
from zuzenaa.demo.dataset import CommitFixture, DemoState, SubmissionSpec
from zuzenaa.repos import paths
from zuzenaa.repos import service as repo_service
from zuzenaa.util import now_epoch


@dataclass
class SeedSummary:
    origins: int
    repos: int
    analyses: int
    errors: int


def git(args: list[str], cwd: Path, *, env: dict[str, str] | None = None) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} falló: {result.stderr.strip()}")
    return result.stdout


def _force_writable(func: Callable[[str], object], path: str, _exc: BaseException) -> None:
    """En Windows git deja los objetos en solo lectura: quítalo y reintenta."""
    os.chmod(path, stat.S_IWRITE)
    func(path)


def _build_origin(
    dest: Path, commits: list[CommitFixture], *, author: str, email: str, today: date
) -> None:
    """Crea un repo git con la historia de una entrega (fechas reales por commit)."""
    if dest.exists():
        shutil.rmtree(dest, onexc=_force_writable)
    dest.mkdir(parents=True)
    git(["init", "--quiet", "-b", "main"], dest)
    git(["config", "user.name", author], dest)
    git(["config", "user.email", email], dest)
    for commit in commits:
        when = dataset.commit_datetime(today, commit["day_offset"], commit["hour"])
        commit_files(dest, commit["files"], message=commit["message"], when=when)


def commit_files(dest: Path, files: dict[str, str], *, message: str, when: datetime) -> str:
    """Escribe ``files`` en el repo ``dest`` y los commitea con fecha ``when``. Devuelve el SHA."""
    for rel, content in files.items():
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    git(["add", "-A"], dest)
    stamp = when.isoformat()
    env = {**os.environ, "GIT_AUTHOR_DATE": stamp, "GIT_COMMITTER_DATE": stamp}
    git(["commit", "--quiet", "-m", message], dest, env=env)
    return git(["rev-parse", "HEAD"], dest).strip()


def commit_shas(repo: Path) -> list[str]:
    """SHAs en orden cronológico (el primero es el commit más antiguo)."""
    out = git(["rev-list", "--reverse", "HEAD"], repo)
    return [line.strip() for line in out.splitlines() if line.strip()]


async def user_names() -> dict[str, str | None]:
    async with SessionLocal() as session:
        rows = (await session.execute(select(User.login, User.name))).all()
    return dict(rows)


def author_for(login: str, state: DemoState, users: dict[str, str | None]) -> tuple[str, str]:
    for student in state.students:
        if student["username"] == login:
            return dataset.student_display_name(student), student["email"]
    return dataset.display_name(login, users.get(login)), f"{login}@ikastola-demo.test"


async def _upsert_repo(
    *,
    org: str,
    classroom: str,
    assignment: str,
    owner: str,
    local: Path,
    head_sha: str,
    committed_at: int,
) -> Repository:
    now = now_epoch()
    async with SessionLocal() as session:
        stmt = select(Repository).where(
            Repository.org == org,
            Repository.classroom == classroom,
            Repository.assignment == assignment,
            Repository.owner == owner,
        )
        row = (await session.execute(stmt)).scalar_one_or_none()
        if row is None:
            row = Repository(
                org=org,
                classroom=classroom,
                assignment=assignment,
                owner=owner,
                repo_full_name=paths.repo_full_name(org, classroom, assignment, owner),
                path=str(local),
                created_at=now,
                updated_at=now,
            )
            session.add(row)
        row.head_sha = head_sha
        row.head_committed_at = committed_at
        row.status = "ok"
        row.detail = None
        row.last_synced_at = now
        row.updated_at = now
        await session.commit()
        await session.refresh(row)
        return row


async def _seed_analyses(
    state: DemoState, assignment: str, owner: str, spec: SubmissionSpec, today: date
) -> int:
    """Analiza las ``analyze_count`` primeras revisiones y deja HEAD en la última."""
    local = paths.repo_path(state.org, dataset.ACTIVE_CLASSROOM, assignment, owner)
    if not (local / ".git").is_dir():
        return 0
    commits = dataset.build_commits(assignment, spec, author=owner)
    shas = commit_shas(local)
    if len(shas) != len(commits):
        raise RuntimeError(
            f"{owner}/{assignment}: se esperaban {len(commits)} commits, hay {len(shas)}"
        )

    analysed = 0
    for index in range(spec.analyze_count):
        when = dataset.commit_datetime(today, commits[index]["day_offset"], commits[index]["hour"])
        stamp = int(when.timestamp())
        git(["checkout", "--quiet", shas[index]], local)
        row = await _upsert_repo(
            org=state.org,
            classroom=dataset.ACTIVE_CLASSROOM,
            assignment=assignment,
            owner=owner,
            local=local,
            head_sha=shas[index],
            committed_at=stamp,
        )
        outcome = await agent_service.analyze_repository(row, created_at=stamp)
        if outcome.status == "analysed":
            analysed += 1

    last = commits[-1]
    last_when = dataset.commit_datetime(today, last["day_offset"], last["hour"])
    git(["checkout", "--quiet", "main"], local)
    await _upsert_repo(
        org=state.org,
        classroom=dataset.ACTIVE_CLASSROOM,
        assignment=assignment,
        owner=owner,
        local=local,
        head_sha=shas[-1],
        committed_at=int(last_when.timestamp()),
    )
    return analysed


async def seed(*, today: date | None = None) -> SeedSummary:
    day = today or datetime.now(UTC).date()
    await init_models()

    state = dataset.default_state(day)
    users = await user_names()
    injected = list(users)
    origins = origins_root()
    origins.mkdir(parents=True, exist_ok=True)

    # 1. «GitHub» ficticio: un repo git local por entrega.
    submissions: list[tuple[str, str, SubmissionSpec]] = [
        (assignment, owner, spec)
        for assignment, per_owner in dataset.SUBMISSIONS.items()
        for owner, spec in per_owner.items()
    ]
    submissions += [
        (assignment, login, spec)
        for assignment, spec in dataset.INJECTED_SUBMISSIONS.items()
        for login in injected
    ]
    for assignment, owner, spec in submissions:
        commits = dataset.build_commits(assignment, spec, author=owner)
        author, email = author_for(owner, state, users)
        dest = origins / state.org / paths.repo_full_name(
            state.org, dataset.ACTIVE_CLASSROOM, assignment, owner
        )
        _build_origin(dest, commits, author=author, email=email, today=day)
        releases.clear(state.org, dest.name)
        for index, sha in enumerate(commit_shas(dest)):
            releases.write(state.org, dest.name, dataset.commit_results(assignment, index, sha))

    # 2. Descarga real (clonado) de cada entrega, como en producción.
    owners = [student["username"] for student in state.students] + injected
    repos = 0
    errors = 0
    for assignment in (dataset.ASSIGNMENT_P1, dataset.ASSIGNMENT_P2):
        summary = await repo_service.sync_assignment(
            org=state.org,
            classroom=dataset.ACTIVE_CLASSROOM,
            assignment=assignment,
            owners=owners,
            token="demo",
            clone_url_template=clone_url_template(),
        )
        repos += summary.cloned + summary.updated
        errors += summary.errors

    # 3. Análisis de las revisiones ya entregadas (fechados en su commit).
    analyses = 0
    for assignment, owner, spec in submissions:
        analyses += await _seed_analyses(state, assignment, owner, spec, day)

    return SeedSummary(
        origins=len(submissions), repos=repos, analyses=analyses, errors=errors
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Siembra el dataset del modo demo de ZuzenAA.")
    parser.parse_args()
    summary = asyncio.run(seed())
    print(
        f"Modo demo sembrado: {summary.origins} origen(es) git, "
        f"{summary.repos} repo(s) descargado(s), {summary.analyses} análisis, "
        f"{summary.errors} error(es) esperado(s)."
    )


if __name__ == "__main__":
    main()