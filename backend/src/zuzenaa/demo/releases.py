"""Releases ficticias del modo demo: el ``result.json`` de los tests por commit.

En Classroom 50 cada push dispara los tests en GitHub Actions y publica una
Release con ``result.json``. En la demo no hay Actions: el seed y el push simulado
escriben ese resultado en ``<DATA_ROOT>/demo-releases/<org>/<repo>/<sha>.json``,
fuera del repo para que no aparezca en el clon.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from zuzenaa.config import settings
from zuzenaa.github.results import TestResults

RELEASES_DIRNAME = "demo-releases"


def releases_root() -> Path:
    return Path(settings.data_root) / RELEASES_DIRNAME


def _repo_dir(org: str, repo_full_name: str) -> Path:
    return releases_root() / org / repo_full_name


def clear(org: str, repo_full_name: str) -> None:
    """Borra las releases de un repo (el seed reconstruye su historia)."""
    shutil.rmtree(_repo_dir(org, repo_full_name), ignore_errors=True)


def write(org: str, repo_full_name: str, results: TestResults) -> Path:
    dest = _repo_dir(org, repo_full_name) / f"{results.commit}.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(results.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    return dest


def read(org: str, repo_full_name: str, commit_sha: str) -> TestResults | None:
    path = _repo_dir(org, repo_full_name) / f"{commit_sha}.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return TestResults.from_dict(data) if isinstance(data, dict) else None


__all__ = ["RELEASES_DIRNAME", "clear", "read", "releases_root", "write"]
