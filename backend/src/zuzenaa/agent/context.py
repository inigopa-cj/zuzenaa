"""Build a bounded, solution-free view of a local repository for the agent.

The worker must reason about the *real* submission, not a generic template.
This module summarises a local clone: file tree, language mix, size signals and
a truncated diff against the previously analysed commit. It describes the code
(it never writes the solution) so any provider can produce grounded feedback.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path

from zuzenaa.repos import git

_IGNORED_DIRS = frozenset(
    {
        ".git", ".hg", ".svn", "node_modules", ".venv", "venv", "__pycache__",
        "target", "build", "dist", "out", ".idea", ".vscode", ".gradle", ".mvn",
        "bin", "obj", ".next", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    }
)

_TEXT_EXTENSIONS = frozenset(
    {
        ".py", ".java", ".kt", ".js", ".jsx", ".ts", ".tsx", ".cs", ".go", ".rs",
        ".c", ".h", ".cpp", ".hpp", ".rb", ".php", ".swift", ".m", ".sql",
        ".html", ".css", ".scss", ".xml", ".json", ".yml", ".yaml", ".toml",
        ".md", ".txt", ".sh", ".properties", ".gradle", ".cfg", ".ini",
    }
)

_LANGUAGE_BY_EXT = {
    ".py": "Python", ".java": "Java", ".kt": "Kotlin", ".js": "JavaScript",
    ".jsx": "JavaScript", ".ts": "TypeScript", ".tsx": "TypeScript",
    ".cs": "C#", ".go": "Go", ".rs": "Rust", ".c": "C", ".h": "C",
    ".cpp": "C++", ".hpp": "C++", ".rb": "Ruby", ".php": "PHP",
    ".swift": "Swift", ".m": "Objective-C", ".sql": "SQL",
    ".html": "HTML", ".css": "CSS", ".scss": "SCSS",
}

_TODO = re.compile(r"\b(TODO|FIXME|XXX)\b")

_MAX_FILES_SCANNED = 2_000
_MAX_FILES_LISTED = 200
_MAX_FILE_BYTES = 1_000_000


@dataclass
class RepoContext:
    file_count: int
    line_count: int
    languages: list[str]
    files: list[dict[str, object]]
    has_tests: bool
    has_readme: bool
    todo_count: int
    largest_files: list[dict[str, object]]
    diff: dict[str, object] | None
    diff_reason: str | None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _iter_files(root: Path) -> list[Path]:
    found: list[Path] = []
    stack = [root]
    while stack and len(found) < _MAX_FILES_SCANNED:
        current = stack.pop()
        try:
            entries = sorted(current.iterdir(), key=lambda p: p.name)
        except OSError:
            continue
        for entry in entries:
            if entry.is_symlink():
                continue
            if entry.is_dir():
                if entry.name in _IGNORED_DIRS:
                    continue
                if entry.name.startswith(".") and entry.name != ".github":
                    continue
                stack.append(entry)
            elif entry.is_file():
                found.append(entry)
                if len(found) >= _MAX_FILES_SCANNED:
                    break
    return found


def _scan_text(path: Path) -> tuple[int, int]:
    """Return (line_count, todo_count) reading the file at most once."""
    lines = 0
    todos = 0
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as handle:
            for line in handle:
                lines += 1
                if _TODO.search(line):
                    todos += 1
    except OSError:
        return 0, 0
    return lines, todos


def _size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


async def build_context(
    root: Path, *, base_sha: str | None, max_diff_chars: int
) -> RepoContext:
    """Summarise the local clone rooted at ``root``.

    ``base_sha`` is the commit of the previous analysis (if any); the diff is
    computed against it and truncated to ``max_diff_chars``.
    """
    languages: set[str] = set()
    listed: list[dict[str, object]] = []
    largest: list[tuple[int, dict[str, object]]] = []
    total_lines = 0
    todo_count = 0
    has_tests = False
    has_readme = False

    files = _iter_files(root)
    for path in files:
        rel = path.relative_to(root).as_posix()
        lower = rel.lower()
        ext = path.suffix.lower()
        size = _size(path)

        if ext in _TEXT_EXTENSIONS and size <= _MAX_FILE_BYTES:
            lines, todos = _scan_text(path)
        else:
            lines, todos = 0, 0

        total_lines += lines
        todo_count += todos
        language = _LANGUAGE_BY_EXT.get(ext)
        if language:
            languages.add(language)
        if "test" in lower or "spec" in lower:
            has_tests = True
        if lower.startswith("readme.") or lower == "readme":
            has_readme = True

        entry: dict[str, object] = {"path": rel, "lines": lines, "size": size}
        if len(listed) < _MAX_FILES_LISTED:
            listed.append(entry)
        largest.append((lines, entry))

    largest.sort(key=lambda item: item[0], reverse=True)

    diff_payload: dict[str, object] | None = None
    diff_reason: str | None = None
    if base_sha:
        try:
            result = await git.diff(root, base_sha, "HEAD", max_chars=max_diff_chars)
        except git.GitError as exc:
            diff_reason = f"no se pudo calcular el diff: {exc}"
        else:
            diff_payload = {
                "base": base_sha[:7],
                "files_changed": result.files_changed,
                "insertions": result.insertions,
                "deletions": result.deletions,
                "truncated": result.truncated,
                "patch": result.patch,
            }

    return RepoContext(
        file_count=len(files),
        line_count=total_lines,
        languages=sorted(languages),
        files=listed,
        has_tests=has_tests,
        has_readme=has_readme,
        todo_count=todo_count,
        largest_files=[entry for _, entry in largest[:5]],
        diff=diff_payload,
        diff_reason=diff_reason,
    )


__all__ = ["RepoContext", "build_context"]
