"""Student surface: the logged-in user's role, assignments and feedback.

Discovery is **local**: whatever the teacher already downloaded/analysed for
this login is what the student sees, so it does not depend on the student's
GitHub token being able to read the Classroom 50 configuration.

Staff can **preview** what a student sees (``?as=<login>``), limited to the
classrooms where they are staff.
"""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select

from zuzenaa.api.deps import CurrentUserDep, GhCliDep
from zuzenaa.auth.roles import resolve_role
from zuzenaa.db.models import Analysis, Repository
from zuzenaa.db.session import SessionLocal
from zuzenaa.progress.service import progress_for

router = APIRouter(prefix="/me", tags=["me"])


class ClassroomRefOut(BaseModel):
    org: str
    classroom: str


class RoleOut(BaseModel):
    login: str
    role: str  # staff | student | unknown
    staff_of: list[ClassroomRefOut]
    owns_repos: bool


class AlertOut(BaseModel):
    kind: str
    text: str


class MyAssignmentOut(BaseModel):
    org: str
    classroom: str
    assignment: str
    owner: str
    repo_full_name: str
    status: str
    head_sha: str | None
    last_synced_at: int | None
    analyses: int
    last_analysis_at: int | None
    # Progreso (mismas métricas que la ficha): lo que el panel del alumno resume.
    passed: int | None = None
    total: int | None = None
    score: int | None = None
    max_score: int | None = None
    last_commit_at: int | None = None
    latest_hint: str | None = None
    summary: str = ""
    alerts: list[AlertOut] = []


@router.get("/role", response_model=RoleOut)
async def my_role(user: CurrentUserDep, gh: GhCliDep) -> RoleOut:
    info = await resolve_role(user.login, gh)
    return RoleOut(
        login=info.login,
        role=info.role,
        staff_of=[ClassroomRefOut(org=r.org, classroom=r.classroom) for r in info.staff_of],
        owns_repos=info.owns_repos,
    )


@router.get("/assignments", response_model=list[MyAssignmentOut])
async def my_assignments(
    user: CurrentUserDep,
    gh: GhCliDep,
    as_login: Annotated[str | None, Query(alias="as")] = None,
) -> list[MyAssignmentOut]:
    login = user.login.lower()
    preview = as_login is not None and as_login.lower() != login
    allowed: set[tuple[str, str]] | None = None
    if preview:
        info = await resolve_role(user.login, gh)
        if not info.staff_of:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Solo el profesorado puede ver la plataforma como un alumno.",
            )
        allowed = {(ref.org, ref.classroom) for ref in info.staff_of}
        login = str(as_login).lower()

    async with SessionLocal() as session:
        repos = (
            await session.execute(
                select(Repository)
                .where(func.lower(Repository.owner) == login)
                .order_by(Repository.classroom, Repository.assignment)
            )
        ).scalars().all()
        counts = {
            repo_id: (count, last)
            for repo_id, count, last in (
                await session.execute(
                    select(
                        Analysis.repository_id,
                        func.count(Analysis.id),
                        func.max(Analysis.created_at),
                    )
                    .where(Analysis.repository_id.in_([repo.id for repo in repos]))
                    .group_by(Analysis.repository_id)
                )
            ).all()
        }

    result: list[MyAssignmentOut] = []
    for repo in repos:
        if allowed is not None and (repo.org, repo.classroom) not in allowed:
            continue
        count, last = counts.get(repo.id, (0, None))
        progress = await progress_for(repo)
        current = progress.current
        result.append(
            MyAssignmentOut(
                org=repo.org,
                classroom=repo.classroom,
                assignment=repo.assignment,
                owner=repo.owner,
                repo_full_name=repo.repo_full_name,
                status=repo.status,
                head_sha=repo.head_sha,
                last_synced_at=repo.last_synced_at,
                analyses=count,
                last_analysis_at=last,
                passed=current.passed if current else None,
                total=current.total if current else None,
                score=current.score if current else None,
                max_score=current.max_score if current else None,
                last_commit_at=progress.rhythm.last_at if progress.rhythm else None,
                latest_hint=progress.latest_hint,
                summary=progress.summary,
                alerts=[AlertOut(kind=a.kind, text=a.text) for a in progress.alerts],
            )
        )
    return result
