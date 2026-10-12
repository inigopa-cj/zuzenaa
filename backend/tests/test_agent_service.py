import json
from pathlib import Path

from zuzenaa.agent import service as agent_service
from zuzenaa.config import settings
from zuzenaa.db.models import Analysis, Repository
from zuzenaa.db.session import SessionLocal, init_models
from zuzenaa.util import now_epoch


async def _make_repo(owner: str, files: dict[str, str]) -> Repository:
    local = Path(settings.data_root) / "org" / "c1" / "a1" / "repos" / owner
    local.mkdir(parents=True, exist_ok=True)
    for name, content in files.items():
        (local / name).write_text(content)
    now = now_epoch()
    async with SessionLocal() as session:
        repo = Repository(
            org="org",
            classroom="c1",
            assignment="a1",
            owner=owner,
            repo_full_name=f"c1-a1-{owner}",
            path=str(local),
            head_sha="a" * 40,
            head_committed_at=now,
            last_synced_at=now,
            status="ok",
            created_at=now,
            updated_at=now,
        )
        session.add(repo)
        await session.commit()
        await session.refresh(repo)
        return repo


async def test_analyze_repository_creates_snapshot_and_analysis() -> None:
    await init_models()
    repo = await _make_repo("ana", {"main.py": "print('hi')"})
    outcome = await agent_service.analyze_repository(repo)
    assert outcome.status == "analysed"
    assert outcome.analysis_id is not None

    snap = Path(repo.path).parent.parent / "snapshots" / "ana"
    dirs = list(snap.iterdir())
    assert len(dirs) == 1
    assert (dirs[0] / "feedback.md").is_file()
    assert (dirs[0] / "main.py").read_text() == "print('hi')"

    feedback_md = (dirs[0] / "feedback.md").read_text()
    assert "1 fichero" in feedback_md
    assert "Python" in feedback_md

    async with SessionLocal() as session:
        rows = (await session.execute(
            Analysis.__table__.select().where(Analysis.repository_id == repo.id)
        )).all()
    assert len(rows) == 1
    stored = json.loads(rows[0].feedback_json)
    assert "funcionalidad" in stored
    assert "1 fichero" in stored["funcionalidad"]


async def test_analyze_repository_caches_same_commit() -> None:
    await init_models()
    repo = await _make_repo("luis", {"main.py": "x"})
    first = await agent_service.analyze_repository(repo)
    second = await agent_service.analyze_repository(repo)
    assert first.status == "analysed"
    assert second.status == "cached"
    assert second.analysis_id == first.analysis_id


async def test_force_reanalyzes() -> None:
    await init_models()
    repo = await _make_repo("eva", {"main.py": "y"})
    await agent_service.analyze_repository(repo)
    forced = await agent_service.analyze_repository(repo, force=True)
    assert forced.status == "analysed"


def _git(cwd: Path, *args: str) -> str:
    import subprocess

    result = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True)
    return result.stdout.strip()


def _commit(origin: Path, name: str, content: str, message: str) -> str:
    (origin / name).write_text(content)
    _git(origin, "add", "-A")
    _git(origin, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", message)
    return _git(origin, "rev-parse", "HEAD")


async def test_sync_and_analyze_picks_up_latest_push(tmp_path: Path) -> None:
    await init_models()
    org, classroom, assignment = "org", "c2", "a2"
    template = tmp_path.as_uri() + "/{org}/{repo}"
    origin = tmp_path / org / f"{classroom}-{assignment}-luis"
    origin.mkdir(parents=True)
    _git(origin, "init", "-q", "-b", "main")
    first = _commit(origin, "main.py", "print('v1')\n", "v1")

    async def analyze(owners: list[str]) -> list[agent_service.AnalyzeOutcome]:
        return await agent_service.sync_and_analyze(
            org=org,
            classroom=classroom,
            assignment=assignment,
            owners=owners,
            token="",
            clone_url_template=template,
        )

    [outcome] = await analyze(["luis"])
    assert (outcome.status, outcome.commit_sha) == ("analysed", first)

    # El alumno hace push: «Analizar» descarga ese commit antes de analizar.
    second = _commit(origin, "main.py", "print('v2')\n", "v2")
    [outcome] = await analyze(["luis"])
    assert (outcome.status, outcome.commit_sha) == ("analysed", second)

    # Sin push nuevo, el mismo commit no se vuelve a analizar.
    [outcome] = await analyze(["luis"])
    assert (outcome.status, outcome.commit_sha) == ("cached", second)

    # Si la descarga falla, no se analiza código viejo.
    [missing] = await analyze(["sin-repo"])
    assert missing.status == "error"
    assert missing.reason is not None and "descargar" in missing.reason
