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
from zuzenaa.github.results import load_test_results
from zuzenaa.privacy import pseudonyms
from zuzenaa.privacy.scrub import leaks, scrub
from zuzenaa.repos import paths
from zuzenaa.repos import service as repo_service
from zuzenaa.util import now_epoch


@dataclass
class AnalyzeOutcome:
    owner: str
    status: str  # analysed | cached | blocked | error
    commit_sha: str | None = None
    analysis_id: int | None = None
    reason: str | None = None


def _build_context(
    *,
    repo: Repository,
    alias: str,
    evolution: str | None,
    code: dict[str, object],
    tests: dict[str, object] | None,
    previous_tests: dict[str, object] | None,
) -> dict[str, object]:
    return {
        "classroom": repo.classroom,
        "assignment": repo.assignment,
        "owner": alias,  # nunca el login: la identidad no sale del backend
        "commit": repo.head_sha,
        "evolution": evolution,
        "repo": code,
        # Resultado de los tests de Classroom 50 para este commit (leído, no ejecutado).
        "tests": tests,
        "previous_tests": previous_tests,
    }


def _stored_tests(analysis: Analysis) -> dict[str, object] | None:
    """Resultado de tests guardado con un análisis anterior (si lo tenía)."""
    try:
        payload = json.loads(analysis.feedback_json)
    except json.JSONDecodeError:
        return None
    tests = payload.get("tests") if isinstance(payload, dict) else None
    return tests if isinstance(tests, dict) else None


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


def _snapshot(repo: Repository, commit_sha: str, *, created_at: int | None = None) -> Path:
    stamp = created_at if created_at is not None else now_epoch()
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
    repo: Repository, *, force: bool = False, created_at: int | None = None
) -> AnalyzeOutcome:
    # ``created_at`` solo lo usa el modo demo, para fechar cada análisis en su
    # commit (el histórico y el progreso ordenan por esta fecha). Por defecto: ahora.
    now = created_at if created_at is not None else now_epoch()
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

    test_results = await load_test_results(
        org=repo.org, repo_full_name=repo.repo_full_name, commit_sha=repo.head_sha
    )
    tests = test_results.to_dict() if test_results is not None else None

    # Privacidad: el agente solo ve el seudónimo. Se sustituyen login y nombre en todo
    # el contexto (código, diff, rutas...) y se verifica que no quede ninguno.
    alias = await pseudonyms.alias_for(repo.org, repo.classroom, repo.owner)
    terms = await pseudonyms.personal_terms(repo.org, repo.classroom, repo.owner)
    context = scrub(
        _build_context(
            repo=repo,
            alias=alias,
            evolution=evolution,
            code=code_context,
            tests=tests,
            previous_tests=_stored_tests(previous) if previous is not None else None,
        ),
        terms,
        alias,
    )
    if leaks(context, terms):
        return AnalyzeOutcome(
            owner=repo.owner,
            status="blocked",
            reason="el contexto contenía datos personales del alumno; no se envía al agente",
        )

    worker = AgentWorker(get_provider())
    result = await worker.run(context if isinstance(context, dict) else {})
    if not result.posted:
        return AnalyzeOutcome(
            owner=repo.owner, status="blocked", reason=result.reason
        )

    snapshot = _snapshot(repo, repo.head_sha, created_at=now)
    (snapshot / "feedback.md").write_text(result.body)

    payload: dict[str, object] = {"provider": result.provider}
    if result.feedback is not None:
        payload |= result.feedback.model_dump()
    if tests is not None:
        payload["tests"] = tests
    feedback_json = json.dumps(payload, ensure_ascii=False)
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


async def sync_and_analyze(
    *,
    org: str,
    classroom: str,
    assignment: str,
    owners: list[str],
    token: str,
    clone_url_template: str | None = None,
    force: bool = False,
) -> list[AnalyzeOutcome]:
    """Descarga el último push de cada alumno y lo analiza.

    Es el camino de «Analizar» y del push (simulado en la demo): siempre se analiza
    el commit más reciente, no lo que hubiera descargado antes. Si el commit ya
    estaba analizado devuelve ``cached`` (salvo ``force``). Si la descarga falla no
    se analiza código viejo: el alumno sale como ``error`` con el motivo.
    """
    await repo_service.sync_assignment(
        org=org,
        classroom=classroom,
        assignment=assignment,
        owners=owners,
        token=token,
        clone_url_template=clone_url_template,
    )
    async with SessionLocal() as session:
        stmt = select(Repository).where(
            Repository.org == org,
            Repository.classroom == classroom,
            Repository.assignment == assignment,
            Repository.owner.in_(owners),
        )
        repos = {row.owner: row for row in (await session.execute(stmt)).scalars().all()}

    outcomes: list[AnalyzeOutcome] = []
    for owner in owners:
        repo = repos.get(owner)
        if repo is None or repo.status == "error":
            detail = repo.detail if repo is not None else None
            outcomes.append(
                AnalyzeOutcome(
                    owner=owner,
                    status="error",
                    reason=f"no se pudo descargar el último push: {detail or 'sin repo'}",
                )
            )
            continue
        outcomes.append(await analyze_repository(repo, force=force))
    return outcomes


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
