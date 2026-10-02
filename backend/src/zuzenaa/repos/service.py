"""Repo Manager: download every student repo of an assignment to disk."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select

from zuzenaa.config import settings
from zuzenaa.db.models import Repository
from zuzenaa.db.session import SessionLocal
from zuzenaa.repos import git, paths
from zuzenaa.util import now_epoch


@dataclass
class SyncSummary:
    total: int
    cloned: int
    updated: int
    skipped: int
    errors: int


async def sync_assignment(
    *,
    org: str,
    classroom: str,
    assignment: str,
    owners: list[str],
    token: str,
    clone_url_template: str = "https://github.com/{org}/{repo}.git",
) -> SyncSummary:
    """Clone/update each owner's repo and record state in the DB."""
    cloned = updated = skipped = errors = 0
    now = now_epoch()

    for owner in owners:
        full_name = paths.repo_full_name(org, classroom, assignment, owner)
        clone_url = clone_url_template.format(org=org, repo=full_name)
        local = paths.repo_path(org, classroom, assignment, owner)
        try:
            result = await git.sync_repo(
                clone_url=clone_url,
                path=local,
                token=token,
                depth=settings.git_clone_depth,
                timeout=settings.git_timeout,
            )
        except git.GitError as exc:
            errors += 1
            await _upsert(
                org, classroom, assignment, owner, full_name, local,
                head_sha=None, committed_at=None, status="error",
                detail=str(exc), now=now,
            )
            continue

        if result.cloned:
            cloned += 1
        else:
            updated += 1
        await _upsert(
            org, classroom, assignment, owner, full_name, local,
            head_sha=result.head_sha, committed_at=result.committed_at,
            status="ok", detail=None, now=now,
        )

    return SyncSummary(
        total=len(owners),
        cloned=cloned,
        updated=updated,
        skipped=skipped,
        errors=errors,
    )


async def _upsert(
    org: str,
    classroom: str,
    assignment: str,
    owner: str,
    full_name: str,
    local: object,
    *,
    head_sha: str | None,
    committed_at: int | None,
    status: str,
    detail: str | None,
    now: int,
) -> None:
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
                repo_full_name=full_name,
                path=str(local),
                created_at=now,
                updated_at=now,
            )
            session.add(row)
        row.head_sha = head_sha or row.head_sha
        row.head_committed_at = committed_at or row.head_committed_at
        row.status = status
        row.detail = detail
        row.last_synced_at = now
        row.updated_at = now
        await session.commit()
