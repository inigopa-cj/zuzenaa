from collections.abc import Mapping, Sequence

import pytest

from zuzenaa.github.cli import GhCli, GhError

_JSON = '[{"short_name": "c1", "name": "C1", "term": "T", "team": {"id": 1, "slug": "s"}}]'


async def _ok_runner(args: Sequence[str], env: Mapping[str, str]) -> tuple[int, str, str]:
    assert list(args)[:4] == ["gh", "teacher", "classroom", "list"]
    assert env["GH_TOKEN"] == "tok"
    return 0, _JSON, "DALP/classroom50: 1 classroom"


async def _fail_runner(args: Sequence[str], env: Mapping[str, str]) -> tuple[int, str, str]:
    return 1, "", "boom"


async def test_classrooms_parses_json_from_stdout() -> None:
    cli = GhCli(token="tok", runner=_ok_runner)
    rooms = await cli.classrooms("org")
    assert [room.short_name for room in rooms] == ["c1"]
    assert rooms[0].team is not None
    assert rooms[0].team.slug == "s"


async def test_classrooms_include_archived_adds_flag() -> None:
    captured: list[list[str]] = []

    async def runner(args: Sequence[str], env: Mapping[str, str]) -> tuple[int, str, str]:
        captured.append(list(args))
        return 0, "[]", ""

    cli = GhCli(token="tok", runner=runner)
    await cli.classrooms("org", include_archived=True)
    assert captured[0][-1] == "--all"


async def test_gh_error_on_nonzero_exit() -> None:
    cli = GhCli(token="tok", runner=_fail_runner)
    with pytest.raises(GhError, match="boom"):
        await cli.classrooms("org")


async def test_invalid_payload_raises() -> None:
    async def runner(args: Sequence[str], env: Mapping[str, str]) -> tuple[int, str, str]:
        return 0, "{}", ""

    cli = GhCli(token="tok", runner=runner)
    with pytest.raises(GhError, match="JSON array"):
        await cli.classrooms("org")


_CSV = (
    "username,first_name,last_name,email,section,github_id,enrollment_status\n"
    "ana,Ana,Beltrán,ana@example.test,A,42,enrolled\n"
    ",,,,,,\n"
)

_CLASSROOMS = (
    '[{"short_name":"c1","name":"C1","team":{"id":1,"slug":"classroom50-c1"}}]'
)


async def test_roster_merges_team_members_with_csv_metadata() -> None:
    async def runner(args: Sequence[str], env: Mapping[str, str]) -> tuple[int, str, str]:
        joined = " ".join(args)
        if "classroom" in joined and "list" in joined:
            return 0, _CLASSROOMS, ""
        if "teams/classroom50-c1/members" in joined:
            # ana (has CSV metadata) + luis (no metadata)
            return 0, '[{"login":"ana"},{"login":"luis"}]', ""
        if "students.csv" in joined:
            return 0, _CSV, ""
        if "roster.csv" in joined:
            return 1, "", "not found"
        return 0, "[]", ""

    cli = GhCli(token="tok", runner=runner)
    students = await cli.roster("org", "c1")
    by_user = {s.username: s for s in students}
    assert set(by_user) == {"ana", "luis"}
    assert by_user["ana"].first_name == "Ana"
    assert by_user["ana"].section == "A"
    assert by_user["luis"].first_name is None
    # sorted by first name / username: Ana then luis
    assert [s.username for s in students] == ["ana", "luis"]


async def test_staff_tolerates_both_namings() -> None:
    async def runner(args: Sequence[str], env: Mapping[str, str]) -> tuple[int, str, str]:
        joined = " ".join(args)
        if "classroom" in joined and "list" in joined:
            return 0, _CLASSROOMS, ""
        if "teams/classroom50-c1-instructor/members" in joined:
            return 0, '[{"login":"prof"}]', ""
        if "teams/classroom50-c1-ta/members" in joined:
            return 0, '[{"login":"ta1"}]', ""
        return 0, "[]", ""

    cli = GhCli(token="tok", runner=runner)
    staff = await cli.staff("org", "c1")
    roles = {s.username: s.role for s in staff}
    assert roles == {"prof": "instructor", "ta1": "ta"}
