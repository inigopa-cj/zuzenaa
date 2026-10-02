"""Student surface: the logged-in user's assignments and feedback.

Discovery is **local**: whatever the teacher already downloaded/analysed for
this login is what the student sees, so it does not depend on the student's
GitHub token being able to read the Classroom 50 configuration.
"""

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import func, select

from zuzenaa.api.deps import CurrentUserDep
from zuzenaa.db.models import Analysis, Repository
from zuzenaa.db.session import SessionLocal

router = APIRouter(prefix="/me", tags=["me"])


class MyAssignmentOut(BaseModel):
    org: str
    classroom: str
    assignment: str
    owner: str
    repo_full_name: str
    head_sha: str | None
    last_synced_at: int | None
    analyses: int
    last_analysis_at: int | None


@router.get("/assignments", response_model=list[MyAssignmentOut])
async def my_assignments(user: CurrentUserDep) -> list[MyAssignmentOut]:
    login = user.login.lower()
    async with SessionLocal() as session:
        repos = (
            await session.execute(
                select(Repository)
                .where(func.lower(Repository.owner) == login)
                .order_by(Repository.classroom, Repository.assignment)
            )
        ).scalars().all()

        result: list[MyAssignmentOut] = []
        for repo in repos:
            count, last = (
                await session.execute(
                    select(func.count(Analysis.id), func.max(Analysis.created_at)).where(
                        Analysis.repository_id == repo.id
                    )
                )
            ).one()
            result.append(
                MyAssignmentOut(
                    org=repo.org,
                    classroom=repo.classroom,
                    assignment=repo.assignment,
                    owner=repo.owner,
                    repo_full_name=repo.repo_full_name,
                    head_sha=repo.head_sha,
                    last_synced_at=repo.last_synced_at,
                    analyses=count,
                    last_analysis_at=last,
                )
            )
    return result
