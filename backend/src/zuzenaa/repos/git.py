"""Git operations on local repositories (clone, fetch, HEAD info)."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path


class GitError(RuntimeError):
    def __init__(self, message: str, *, stderr: str = "") -> None:
        super().__init__(message)
        self.stderr = stderr


@dataclass
class GitResult:
    cloned: bool
    head_sha: str
    committed_at: int | None


@dataclass
class CommitInfo:
    sha: str
    committed_at: int
    files_changed: int
    insertions: int
    deletions: int


@dataclass
class GitDiff:
    files_changed: int
    insertions: int
    deletions: int
    patch: str
    truncated: bool


async def _run_git(args: list[str], *, cwd: Path | None, timeout: float) -> tuple[int, str, str]:
    process = await asyncio.create_subprocess_exec(
        "git",
        *args,
        cwd=str(cwd) if cwd else None,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
    except TimeoutError as exc:
        process.kill()
        raise GitError(f"git {args[0]} timed out") from exc
    return process.returncode or 0, stdout.decode(), stderr.decode()


async def _head_info(repo: Path) -> tuple[str, int | None]:
    _, sha, _ = await _run_git(["rev-parse", "HEAD"], cwd=repo, timeout=30)
    committed_at: int | None = None
    code, out, _ = await _run_git(["log", "-1", "--format=%ct"], cwd=repo, timeout=30)
    if code == 0 and out.strip().isdigit():
        committed_at = int(out.strip())
    return sha.strip(), committed_at


async def sync_repo(
    *,
    clone_url: str,
    path: Path,
    token: str,
    depth: int = 0,
    timeout: float = 300.0,
) -> GitResult:
    """Clone a repo if missing, else fetch. Returns clone flag and HEAD info."""
    authed_url = _with_token(clone_url, token)
    if not (path / ".git").is_dir():
        path.parent.mkdir(parents=True, exist_ok=True)
        args = ["clone"]
        if depth > 0:
            args += ["--depth", str(depth)]
        args += [authed_url, str(path)]
        code, _, err = await _run_git(args, cwd=None, timeout=timeout)
        if code != 0:
            raise GitError(f"git clone falló: {err.strip()}", stderr=err)
        sha, committed_at = await _head_info(path)
        return GitResult(cloned=True, head_sha=sha, committed_at=committed_at)

    code, _, err = await _run_git(["fetch", "--all", "--prune"], cwd=path, timeout=timeout)
    if code != 0:
        raise GitError(f"git fetch falló: {err.strip()}", stderr=err)
    # El fetch solo trae los commits: hay que mover el árbol de trabajo a la rama
    # remota para que el análisis vea el último push (también tras un force-push).
    await _reset_to_remote(path, timeout=timeout)
    sha, committed_at = await _head_info(path)
    return GitResult(cloned=False, head_sha=sha, committed_at=committed_at)


async def _reset_to_remote(repo: Path, *, timeout: float) -> None:
    """Deja el clon local igual que la rama por defecto del remoto."""
    err = ""
    for target in ("origin/HEAD", "@{upstream}"):
        args = ["reset", "--hard", "--quiet", target]
        code, _, err = await _run_git(args, cwd=repo, timeout=timeout)
        if code == 0:
            return
    raise GitError(f"git reset falló: {err.strip()}", stderr=err)


async def diff(
    repo: Path,
    base: str,
    head: str = "HEAD",
    *,
    max_chars: int = 20_000,
    timeout: float = 60.0,
) -> GitDiff:
    """Bounded diff between two commits of a local clone.

    Returns the change summary plus a patch truncated to ``max_chars`` so the
    agent can inspect *what changed* without unbounded cost.
    """
    stat_args = ["diff", "--no-color", "--no-ext-diff", "--numstat", base, head]
    code, out, err = await _run_git(stat_args, cwd=repo, timeout=timeout)
    if code != 0:
        raise GitError(f"git diff falló: {err.strip()}", stderr=err)

    files_changed = insertions = deletions = 0
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) != 3:
            continue
        files_changed += 1
        if parts[0].isdigit():
            insertions += int(parts[0])
        if parts[1].isdigit():
            deletions += int(parts[1])

    patch_args = ["diff", "--no-color", "--no-ext-diff", base, head]
    code, out, err = await _run_git(patch_args, cwd=repo, timeout=timeout)
    if code != 0:
        raise GitError(f"git diff falló: {err.strip()}", stderr=err)

    truncated = len(out) > max_chars
    return GitDiff(
        files_changed=files_changed,
        insertions=insertions,
        deletions=deletions,
        patch=out[:max_chars],
        truncated=truncated,
    )


_LOG_MARK = "@@zuzenaa@@"


async def log(repo: Path, *, max_commits: int = 500, timeout: float = 60.0) -> list[CommitInfo]:
    """Historia de HEAD (del más antiguo al más reciente) con el tamaño de cada commit.

    Incluye también los commits que nunca se analizaron: es la base del ritmo de
    trabajo en el progreso del alumno.
    """
    args = [
        "log", "--no-color", f"--max-count={max_commits}", "--reverse",
        f"--format={_LOG_MARK}%H %ct", "--numstat",
    ]
    code, out, err = await _run_git(args, cwd=repo, timeout=timeout)
    if code != 0:
        raise GitError(f"git log falló: {err.strip()}", stderr=err)

    commits: list[CommitInfo] = []
    for line in out.splitlines():
        if line.startswith(_LOG_MARK):
            sha, _, stamp = line[len(_LOG_MARK):].partition(" ")
            commits.append(CommitInfo(sha, int(stamp) if stamp.isdigit() else 0, 0, 0, 0))
            continue
        parts = line.split("\t")
        if len(parts) != 3 or not commits:
            continue
        current = commits[-1]
        current.files_changed += 1
        current.insertions += int(parts[0]) if parts[0].isdigit() else 0
        current.deletions += int(parts[1]) if parts[1].isdigit() else 0
    return commits


def _with_token(clone_url: str, token: str) -> str:
    if clone_url.startswith("https://") and token:
        return clone_url.replace("https://", f"https://x-access-token:{token}@", 1)
    return clone_url
