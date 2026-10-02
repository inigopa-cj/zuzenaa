"""Filesystem layout for downloaded repositories and snapshots.

```
<DATA_ROOT>/<org>/<classroom>/<assignment>/
  repos/<owner>/                     # full git clone
  snapshots/<owner>/<fecha>-<sha>/   # frozen copy per analysis
  analyses.json                      # portable index
```
"""

from __future__ import annotations

import re
from pathlib import Path

from zuzenaa.config import settings

_SAFE = re.compile(r"[^a-z0-9._-]+")


def sanitize(value: str) -> str:
    """Normalise a path segment to a safe, lowercase token."""
    cleaned = _SAFE.sub("-", value.strip().lower()).strip("-.")
    return cleaned or "unknown"


def repo_full_name(org: str, classroom: str, assignment: str, owner: str) -> str:
    """Classroom 50 student repo name: <classroom>-<assignment>-<owner>."""
    return f"{classroom}-{assignment}-{owner}".lower()


def assignment_root(org: str, classroom: str, assignment: str) -> Path:
    return Path(settings.data_root) / sanitize(org) / sanitize(classroom) / sanitize(assignment)


def repos_dir(org: str, classroom: str, assignment: str) -> Path:
    return assignment_root(org, classroom, assignment) / "repos"


def repo_path(org: str, classroom: str, assignment: str, owner: str) -> Path:
    return repos_dir(org, classroom, assignment) / sanitize(owner)


def snapshots_dir(org: str, classroom: str, assignment: str, owner: str) -> Path:
    return (
        assignment_root(org, classroom, assignment)
        / "snapshots"
        / sanitize(owner)
    )


def analyses_index_path(org: str, classroom: str, assignment: str) -> Path:
    return assignment_root(org, classroom, assignment) / "analyses.json"
