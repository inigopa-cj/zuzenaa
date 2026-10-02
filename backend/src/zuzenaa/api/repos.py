"""Repository download endpoints (Repo Manager)."""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select

from zuzenaa.api.deps import GhCliDep
from zuzenaa.db.models import Repository
from zuzenaa.db.session import SessionLocal
from zuzenaa.github.cli import GhError
from zuzenaa.repos import service as repo_service

router = APIRouter(
    prefix="/orgs/{org}/classrooms/{classroom}/assignments/{assignment}",
    tags=["repos"],
)


class RepositoryOut(BaseModel):
    id: int
    owner: str
    repo_full_name: str
    head_sha: str | None
    head_committed_at: int | None
    last_synced_at: int | None
    status: str
    detail: str | None


class SyncOut(BaseModel):
    total: int
    cloned: int
    updated: int
    skipped: int
    errors: int


@router.get("/repos", response_model=list[RepositoryOut])
async def list_repos(
    org: str, classroom: str, assignment: str
) -> list[RepositoryOut]:
    async with SessionLocal() as session:
        stmt = (
            select(Repository)
            .where(
                Repository.org == org,
                Repository.classroom == classroom,
                Repository.assignment == assignment,
            )
            .order_by(Repository.owner)
        )
        rows = (await session.execute(stmt)).scalars().all()
    return [
        RepositoryOut(
            id=row.id,
            owner=row.owner,
            repo_full_name=row.repo_full_name,
            head_sha=row.head_sha,
            head_committed_at=row.head_committed_at,
            last_synced_at=row.last_synced_at,
            status=row.status,
            detail=row.detail,
        )
        for row in rows
    ]


@router.post("/repos/sync", response_model=SyncOut, status_code=status.HTTP_202_ACCEPTED)
async def sync_repos(
    org: str, classroom: str, assignment: str, gh: GhCliDep
) -> SyncOut:
    try:
        students = await gh.roster(org, classroom)
    except GhError as exc:
        raise HTTPException(status_code=502, detail=f"gh teacher falló: {exc}") from exc
    owners = [s.username for s in students]
    if not owners:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El roster está vacío: no hay repos que descargar.",
        )
    summary = await repo_service.sync_assignment(
        org=org, classroom=classroom, assignment=assignment, owners=owners, token=gh.token
    )
    return SyncOut(
        total=summary.total,
        cloned=summary.cloned,
        updated=summary.updated,
        skipped=summary.skipped,
        errors=summary.errors,
    )
