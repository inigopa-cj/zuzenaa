"""Analysis endpoints: run the local agent and read feedback history."""

import json

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ValidationError
from sqlalchemy import select

from zuzenaa.agent import service as agent_service
from zuzenaa.api.deps import GhCliDep, OptionalUserDep
from zuzenaa.config import settings
from zuzenaa.db.models import Analysis, Repository, User
from zuzenaa.db.session import SessionLocal
from zuzenaa.github.cli import GhCli, GhError

router = APIRouter(
    prefix="/orgs/{org}/classrooms/{classroom}/assignments/{assignment}",
    tags=["analysis"],
)


class AnalyzeRequest(BaseModel):
    owner: str | None = None  # None = todos
    force: bool = False  # reanalizar aunque el commit ya esté analizado


class AnalyzeOutcomeOut(BaseModel):
    owner: str
    status: str  # analysed | cached | blocked | error
    commit_sha: str | None = None
    analysis_id: int | None = None
    reason: str | None = None


class HintOut(BaseModel):
    level: int
    text: str


class FeedbackOut(BaseModel):
    funcionalidad: str
    calidad: str
    diseno: str
    pista: HintOut
    teoria: str | None = None


class AnalysisOut(BaseModel):
    id: int
    owner: str
    commit_sha: str
    commit_committed_at: int | None
    created_at: int
    provider: str
    feedback_md: str
    feedback: FeedbackOut | None = None
    evolution: str | None


async def _authorize_owner(
    *, org: str, classroom: str, owner: str, user: User | None, gh: GhCli
) -> None:
    """Allow the owner to read their own feedback, and classroom staff anyone's.

    Without a session, only the local dev shortcut (``allow_env_token``) is
    accepted. Anything else is denied, so a student can't read others' feedback.
    """
    if user is not None and user.login.lower() == owner.lower():
        return
    if user is None:
        if settings.allow_env_token:
            return
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No autenticado.")
    try:
        staff = await gh.staff(org, classroom)
    except GhError:
        staff = []
    if any(member.username.lower() == user.login.lower() for member in staff):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="No tienes acceso al feedback de otro alumno.",
    )


def _feedback(analysis: Analysis) -> FeedbackOut | None:
    """Parse the structured feedback stored alongside the render (if any)."""
    try:
        payload = json.loads(analysis.feedback_json)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    try:
        return FeedbackOut.model_validate(payload)
    except ValidationError:
        return None


async def _repositories(
    org: str, classroom: str, assignment: str, owner: str | None
) -> list[Repository]:
    async with SessionLocal() as session:
        stmt = select(Repository).where(
            Repository.org == org,
            Repository.classroom == classroom,
            Repository.assignment == assignment,
        )
        if owner:
            stmt = stmt.where(Repository.owner == owner)
        return list((await session.execute(stmt)).scalars().all())


@router.post("/analysis", response_model=list[AnalyzeOutcomeOut])
async def run_analysis(
    org: str, classroom: str, assignment: str, payload: AnalyzeRequest
) -> list[AnalyzeOutcomeOut]:
    repos = await _repositories(org, classroom, assignment, payload.owner)
    if not repos:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No hay repos descargados para ese assignment (descárgalos primero).",
        )
    outcomes = []
    for repo in repos:
        outcome = await agent_service.analyze_repository(repo, force=payload.force)
        outcomes.append(
            AnalyzeOutcomeOut(
                owner=outcome.owner,
                status=outcome.status,
                commit_sha=outcome.commit_sha,
                analysis_id=outcome.analysis_id,
                reason=outcome.reason,
            )
        )
    return outcomes


@router.get("/repos/{owner}/analyses", response_model=list[AnalysisOut])
async def owner_history(
    org: str,
    classroom: str,
    assignment: str,
    owner: str,
    user: OptionalUserDep,
    gh: GhCliDep,
) -> list[AnalysisOut]:
    await _authorize_owner(org=org, classroom=classroom, owner=owner, user=user, gh=gh)
    async with SessionLocal() as session:
        stmt = (
            select(Repository).where(
                Repository.org == org,
                Repository.classroom == classroom,
                Repository.assignment == assignment,
                Repository.owner == owner,
            )
        )
        repo = (await session.execute(stmt)).scalar_one_or_none()
        if repo is None:
            raise HTTPException(status_code=404, detail="repo no encontrado")
        analyses = (
            await session.execute(
                select(Analysis)
                .where(Analysis.repository_id == repo.id)
                .order_by(Analysis.created_at.desc())
            )
        ).scalars().all()
    return [
        AnalysisOut(
            id=a.id,
            owner=owner,
            commit_sha=a.commit_sha,
            commit_committed_at=a.commit_committed_at,
            created_at=a.created_at,
            provider=a.provider,
            feedback_md=a.feedback_md,
            feedback=_feedback(a),
            evolution=a.evolution,
        )
        for a in analyses
    ]
