"""Repository download endpoints (Repo Manager)."""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select

from zuzenaa.api.analyses import require_staff
from zuzenaa.api.deps import GhCliDep, OptionalUserDep
from zuzenaa.config import settings
from zuzenaa.db.models import Repository
from zuzenaa.db.session import SessionLocal
from zuzenaa.github.cli import GhError
from zuzenaa.privacy import pseudonyms
from zuzenaa.repos import service as repo_service

router = APIRouter(
    prefix="/orgs/{org}/classrooms/{classroom}/assignments/{assignment}",
    tags=["repos"],
)


class RepositoryOut(BaseModel):
    id: int
    owner: str  # seudónimo (nunca el login)
    repo_label: str  # <clase>-<assignment>-<seudónimo>
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
    org: str, classroom: str, assignment: str, user: OptionalUserDep, gh: GhCliDep
) -> list[RepositoryOut]:
    await require_staff(org=org, classroom=classroom, user=user, gh=gh)
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
    names = await pseudonyms.aliases_for_logins(org, classroom, [row.owner for row in rows])
    out = [
        RepositoryOut(
            id=row.id,
            owner=names[row.owner.lower()],
            repo_label=f"{classroom}-{assignment}-{names[row.owner.lower()]}",
            head_sha=row.head_sha,
            head_committed_at=row.head_committed_at,
            last_synced_at=row.last_synced_at,
            status=row.status,
            detail=await pseudonyms.scrub_text(org, classroom, row.owner, row.detail),
        )
        for row in rows
    ]
    # Orden de lista de clase (posición del seudónimo), no alfabético por login.
    return sorted(out, key=lambda r: int(r.owner.split(".", 1)[0]))


@router.post("/repos/sync", response_model=SyncOut, status_code=status.HTTP_202_ACCEPTED)
async def sync_repos(
    org: str, classroom: str, assignment: str, user: OptionalUserDep, gh: GhCliDep
) -> SyncOut:
    await require_staff(org=org, classroom=classroom, user=user, gh=gh)
    try:
        students = await gh.roster(org, classroom)
    except GhError as exc:
        raise HTTPException(status_code=502, detail=f"gh teacher falló: {exc}") from exc
    # Fija los seudónimos con el roster (nombres → iniciales) antes de nada.
    await pseudonyms.ensure_roster(org, classroom, students)
    owners = [s.username for s in students]
    if not owners:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El roster está vacío: no hay repos que descargar.",
        )
    summary = await repo_service.sync_assignment(
        org=org,
        classroom=classroom,
        assignment=assignment,
        owners=owners,
        token=gh.token,
        clone_url_template=settings.git_clone_url_template,
    )
    return SyncOut(
        total=summary.total,
        cloned=summary.cloned,
        updated=summary.updated,
        skipped=summary.skipped,
        errors=summary.errors,
    )
