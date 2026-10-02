"""Agent service: analyse a locally-downloaded repository and store feedback.

No GitHub publishing: the result lives in the DB and on disk (snapshot +
``feedback.md``). Analysis is separate from downloading.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select

from zuzenaa.agent import AgentWorker, get_provider
from zuzenaa.agent import context as agent_context
from zuzenaa.config import settings
from zuzenaa.db.models import Analysis, Repository
from zuzenaa.db.session import SessionLocal
from zuzenaa.repos import paths
from zuzenaa.util import now_epoch


@dataclass
class AnalyzeOutcome:
    owner: str
    status: str  # analysed | cached | blocked | error
    commit_sha: str | None = None
    analysis_id: int | None = None
    reason: str | None = None


def _build_context(
    *, repo: Repository, evolution: str | None, code: dict[str, object]
) -> dict[str, object]:
    return {
        "classroom": repo.classroom,
        "assignment": repo.assignment,
        "owner": repo.owner,
        "commit": repo.head_sha,
        "evolution": evolution,
        "repo": code,
    }


def _previous_summary(previous: Analysis) -> str:
    """Short, solution-free recap of the previous feedback for evolution."""
    try:
        payload = json.loads(previous.feedback_json)
    except json.JSONDecodeError:
        return previous.feedback_md[:1000]
    if isinstance(payload, dict) and "funcionalidad" in payload:
        parts = [str(payload.get(key, "")) for key in ("funcionalidad", "calidad", "diseno")]
        return " ".join(part for part in parts if part)[:1000]
    return previous.feedback_md[:1000]


def _snapshot(
    repo: Repository, commit_sha: str
) -> Path:
    stamp = now_epoch()
    dest = paths.snapshots_dir(repo.org, repo.classroom, repo.assignment, repo.owner) / (
        f"{stamp}-{commit_sha[:7]}"
    )
    dest.mkdir(parents=True, exist_ok=True)
    source = Path(repo.path)
    for item in source.iterdir():
        if item.name == ".git":
            continue
        target = dest / item.name
        if item.is_dir():
            shutil.copytree(item, target, dirs_exist_ok=True)
        else:
            shutil.copy2(item, target)
    return dest


async def _previous_analysis(repository_id: int, commit_sha: str) -> Analysis | None:
    async with SessionLocal() as session:
        stmt = (
            select(Analysis)
            .where(Analysis.repository_id == repository_id, Analysis.commit_sha != commit_sha)
            .order_by(Analysis.created_at.desc())
            .limit(1)
        )
        return (await session.execute(stmt)).scalar_one_or_none()


async def analyze_repository(
    repo: Repository, *, force: bool = False
) -> AnalyzeOutcome:
    if not repo.head_sha:
        return AnalyzeOutcome(owner=repo.owner, status="error", reason="repo sin HEAD")
    if not Path(repo.path).is_dir():
        return AnalyzeOutcome(owner=repo.owner, status="error", reason="repo no descargado")

    if not force:
        async with SessionLocal() as session:
            stmt = select(Analysis).where(
                Analysis.repository_id == repo.id,
                Analysis.commit_sha == repo.head_sha,
                Analysis.forced.is_(False),
            )
            existing = (await session.execute(stmt)).scalar_one_or_none()
        if existing is not None:
            return AnalyzeOutcome(
                owner=repo.owner,
                status="cached",
                commit_sha=repo.head_sha,
                analysis_id=existing.id,
            )

    previous = await _previous_analysis(repo.id, repo.head_sha)
    evolution = None
    if previous is not None:
        evolution = f"Análisis anterior en {previous.commit_sha[:7]}."

    code = await agent_context.build_context(
        Path(repo.path),
        base_sha=previous.commit_sha if previous is not None else None,
        max_diff_chars=settings.agent_max_diff_chars,
    )
    code_context = code.to_dict()
    if previous is not None:
        code_context["previous_feedback"] = _previous_summary(previous)

    worker = AgentWorker(get_provider())
    result = await worker.run(
        _build_context(repo=repo, evolution=evolution, code=code_context)
    )
    if not result.posted:
        return AnalyzeOutcome(
            owner=repo.owner, status="blocked", reason=result.reason
        )

    snapshot = _snapshot(repo, repo.head_sha)
    (snapshot / "feedback.md").write_text(result.body)

    payload: dict[str, object] = {"provider": result.provider}
    if result.feedback is not None:
        payload |= result.feedback.model_dump()
    feedback_json = json.dumps(payload, ensure_ascii=False)
    now = now_epoch()
    async with SessionLocal() as session:
        analysis = Analysis(
            repository_id=repo.id,
            commit_sha=repo.head_sha,
            commit_committed_at=repo.head_committed_at,
            snapshot_path=str(snapshot),
            provider=result.provider,
            feedback_json=feedback_json,
            feedback_md=result.body,
            evolution=evolution,
            forced=force,
            created_at=now,
        )
        session.add(analysis)
        await session.commit()
        await session.refresh(analysis)
        analysis_id = analysis.id

    _append_index(repo, commit_sha=repo.head_sha, created_at=now, provider=result.provider)
    return AnalyzeOutcome(
        owner=repo.owner,
        status="analysed",
        commit_sha=repo.head_sha,
        analysis_id=analysis_id,
    )


def _append_index(repo: Repository, *, commit_sha: str, created_at: int, provider: str) -> None:
    """Keep a portable ``analyses.json`` next to the repos."""
    index_path = paths.analyses_index_path(repo.org, repo.classroom, repo.assignment)
    index_path.parent.mkdir(parents=True, exist_ok=True)
    data: dict[str, list[dict[str, object]]] = {}
    if index_path.is_file():
        try:
            data = json.loads(index_path.read_text())
        except json.JSONDecodeError:
            data = {}
    data.setdefault(repo.owner, []).append(
        {
            "commit": commit_sha,
            "created_at": created_at,
            "provider": provider,
        }
    )
    index_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
