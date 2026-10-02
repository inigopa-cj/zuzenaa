import subprocess
from pathlib import Path

from zuzenaa.agent.context import build_context


def _write(root: Path, rel: str, content: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


async def test_build_context_summarises_tree(tmp_path: Path) -> None:
    _write(tmp_path, "src/main.py", "print('hi')\n")
    _write(tmp_path, "src/util.py", "# TODO: split this\n")
    _write(tmp_path, "tests/test_main.py", "def test_x():\n    assert True\n")
    _write(tmp_path, "README.md", "# Proyecto\n")
    _write(tmp_path, "node_modules/pkg/index.js", "module.exports = 1\n")

    context = await build_context(tmp_path, base_sha=None, max_diff_chars=1000)

    assert context.file_count == 4
    assert context.has_tests is True
    assert context.has_readme is True
    assert context.todo_count == 1
    assert "Python" in context.languages
    assert context.diff is None
    paths = {entry["path"] for entry in context.files}
    assert "src/main.py" in paths
    assert not any("node_modules" in str(path) for path in paths)


async def test_build_context_without_git_reports_reason(tmp_path: Path) -> None:
    _write(tmp_path, "main.py", "print('hi')\n")
    context = await build_context(tmp_path, base_sha="a" * 40, max_diff_chars=1000)
    assert context.diff is None
    assert context.diff_reason is not None


async def test_build_context_computes_bounded_diff(tmp_path: Path) -> None:
    _git(tmp_path, "init", "-q")
    _write(tmp_path, "main.py", "print('hi')\n")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "-c", "user.name=t", "-c", "user.email=t@e", "commit", "-qm", "one")
    base = _git(tmp_path, "rev-parse", "HEAD")

    _write(tmp_path, "main.py", "print('hi')\nprint('bye')\n")
    _write(tmp_path, "new.py", "x = 1\n")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "-c", "user.name=t", "-c", "user.email=t@e", "commit", "-qm", "two")

    context = await build_context(tmp_path, base_sha=base, max_diff_chars=10_000)

    assert context.diff is not None
    assert context.diff["files_changed"] == 2
    insertions = context.diff["insertions"]
    assert isinstance(insertions, int)
    assert insertions >= 2
    patch = context.diff["patch"]
    assert isinstance(patch, str)
    assert "main.py" in patch
