"""Read-only adapter around the Classroom 50 ``gh teacher`` CLI.

ZuzenAA does **not** manage Classroom 50; it only reads its state (classrooms,
assignments, roster) to know what to download. ``--json`` output is read from
**stdout only**; the human summary (stderr) is ignored (verified against v1.56.1).
"""

from __future__ import annotations

import asyncio
import csv
import io
import json
import os
import tempfile
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, field

from zuzenaa.github.models import (
    Assignment,
    Classroom,
    Org,
    Student,
    TemplateRepo,
)


class GhError(RuntimeError):
    """Raised when a ``gh`` invocation exits non-zero, times out, or misbehaves."""

    def __init__(self, message: str, *, stderr: str = "", returncode: int = 1) -> None:
        super().__init__(message)
        self.stderr = stderr
        self.returncode = returncode


Runner = Callable[[Sequence[str], Mapping[str, str]], Awaitable[tuple[int, str, str]]]


async def _subprocess_runner(
    args: Sequence[str], env: Mapping[str, str]
) -> tuple[int, str, str]:
    process = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=dict(env),
    )
    stdout, stderr = await process.communicate()
    return (process.returncode or 0, stdout.decode(), stderr.decode())


def _first(row: dict[str, str], *keys: str) -> str | None:
    for key in keys:
        value = (row.get(key) or "").strip()
        if value:
            return value
    return None


def _parse_roster_csv(raw: str) -> list[Student]:
    """Parse a classroom roster CSV (roster.csv/students.csv), tolerant of aliases."""
    students: list[Student] = []
    for row in csv.DictReader(io.StringIO(raw)):
        username = _first(row, "username", "login", "github_username")
        if username is None:
            continue
        raw_id = _first(row, "github_id", "id")
        github_id = int(raw_id) if raw_id and raw_id.isdigit() else None
        students.append(
            Student(
                username=username,
                first_name=_first(row, "first_name"),
                last_name=_first(row, "last_name"),
                email=_first(row, "email"),
                section=_first(row, "section"),
                github_id=github_id,
                role=_first(row, "role"),
            )
        )
    return students


@dataclass
class GhCli:
    token: str
    gh_binary: str = "gh"
    timeout: float = 60.0
    runner: Runner = field(default=_subprocess_runner)

    async def _run(self, args: Sequence[str], *, timeout: float | None = None) -> str:
        limit = timeout if timeout is not None else self.timeout
        with tempfile.TemporaryDirectory(prefix="zuzenaa-gh-") as config_dir:
            env: dict[str, str] = {
                **os.environ,
                "GH_TOKEN": self.token,
                "GH_CONFIG_DIR": config_dir,
                "GH_PROMPT_DISABLED": "1",
                "NO_COLOR": "1",
            }
            command = [self.gh_binary, *args]
            try:
                returncode, stdout, stderr = await asyncio.wait_for(
                    self.runner(command, env), timeout=limit
                )
            except TimeoutError as exc:
                raise GhError(f"gh {' '.join(args)} timed out after {limit:g}s") from exc

        if returncode != 0:
            message = stderr.strip() or f"gh exited with code {returncode}"
            raise GhError(message, stderr=stderr, returncode=returncode)
        return stdout

    async def orgs(self) -> list[Org]:
        raw = await self._run(["api", "user/orgs?per_page=100"])
        payload = json.loads(raw)
        if not isinstance(payload, list):
            raise GhError("unexpected orgs payload: expected a JSON array")
        return [Org.model_validate(item) for item in payload]

    async def classrooms(self, org: str, *, include_archived: bool = False) -> list[Classroom]:
        args = ["teacher", "classroom", "list", org, "--json"]
        if include_archived:
            args.append("--all")
        payload = json.loads(await self._run(args))
        if not isinstance(payload, list):
            raise GhError("unexpected classroom list payload: expected a JSON array")
        return [Classroom.model_validate(item) for item in payload]

    async def assignments(self, org: str, classroom: str) -> list[Assignment]:
        raw = await self._run(["teacher", "assignment", "list", org, classroom, "--json"])
        payload = json.loads(raw)
        if not isinstance(payload, list):
            raise GhError("unexpected assignment list payload: expected a JSON array")
        return [Assignment.model_validate(item) for item in payload]

    async def templates(self, org: str) -> list[TemplateRepo]:
        raw = await self._run(
            ["api", f"orgs/{org}/repos?per_page=100&type=all",
             "--jq", "[.[] | select(.is_template == true)]"]
        )
        payload = json.loads(raw)
        if not isinstance(payload, list):
            raise GhError("unexpected templates payload: expected a JSON array")
        result: list[TemplateRepo] = []
        for item in payload:
            full_name = str(item.get("full_name") or "")
            owner, _, name = full_name.partition("/")
            result.append(
                TemplateRepo(
                    owner=str(item.get("owner", {}).get("login") or owner),
                    name=str(item.get("name") or name),
                    full_name=full_name,
                    private=bool(item.get("private")),
                    default_branch=str(item.get("default_branch") or "main"),
                    description=item.get("description"),
                )
            )
        return result

    async def roster(self, org: str, classroom: str) -> list[Student]:
        """Classroom roster: the GitHub **team** is the authority; CSV enriches it."""
        members = await self._classroom_member_logins(org, classroom)
        metadata = await self._roster_metadata(org, classroom)
        students: list[Student] = []
        seen: set[str] = set()
        for login in members:
            seen.add(login.lower())
            meta = metadata.get(login.lower())
            students.append(
                meta.model_copy(update={"username": login}) if meta else Student(username=login)
            )
        for key, meta in metadata.items():
            if key not in seen:
                students.append(meta)
        students.sort(key=lambda s: (s.first_name or s.username).lower())
        return students

    async def staff(self, org: str, classroom: str) -> list[Student]:
        room = await self._classroom(org, classroom)
        base = room.team.slug if room and room.team else f"classroom50-{classroom}"
        role_slugs = [
            ("instructor", f"{base}-instructor"),
            ("teacher", f"{base}-teacher"),
            ("hta", f"{base}-hta"),
            ("ta", f"{base}-ta"),
        ]
        staff: list[Student] = []
        seen: set[str] = set()
        for role, slug in role_slugs:
            for login in await self._team_member_logins(org, slug):
                if login.lower() in seen:
                    continue
                seen.add(login.lower())
                staff.append(Student(username=login, role=role))
        return staff

    async def _classroom(self, org: str, classroom: str) -> Classroom | None:
        rooms = await self.classrooms(org)
        return next((room for room in rooms if room.short_name == classroom), None)

    async def _classroom_member_logins(self, org: str, classroom: str) -> list[str]:
        room = await self._classroom(org, classroom)
        slug = room.team.slug if room and room.team else f"classroom50-{classroom}"
        return await self._team_member_logins(org, slug)

    async def _team_member_logins(self, org: str, slug: str) -> list[str]:
        try:
            raw = await self._run(["api", f"orgs/{org}/teams/{slug}/members?per_page=100"])
        except GhError:
            return []
        payload = json.loads(raw)
        if not isinstance(payload, list):
            return []
        return [str(item["login"]) for item in payload if "login" in item]

    async def _roster_metadata(self, org: str, classroom: str) -> dict[str, Student]:
        for filename in ("roster.csv", "students.csv"):
            path = f"{classroom}/{filename}"
            try:
                raw = await self._run(
                    ["api", f"repos/{org}/classroom50/contents/{path}",
                     "-H", "Accept: application/vnd.github.raw"]
                )
            except GhError:
                continue
            parsed = _parse_roster_csv(raw)
            if parsed:
                return {s.username.lower(): s for s in parsed if s.username}
        return {}
