from zuzenaa.repos import paths


def test_sanitize_strips_unsafe() -> None:
    assert paths.sanitize("DALP-CiudadJardin") == "dalp-ciudadjardin"
    assert paths.sanitize("../../etc/passwd") == "etc-passwd"
    assert paths.sanitize("") == "unknown"


def test_repo_full_name() -> None:
    assert paths.repo_full_name("Org", "dalp-test", "p2", "Ana") == "dalp-test-p2-ana"


def test_layout_paths(tmp_path: object) -> None:
    root = paths.assignment_root("org", "c1", "a1")
    assert root.as_posix().endswith("org/c1/a1")
    assert paths.repo_path("org", "c1", "a1", "ana").name == "ana"
    assert paths.snapshots_dir("org", "c1", "a1", "ana").parent.name == "snapshots"
    assert paths.analyses_index_path("org", "c1", "a1").name == "analyses.json"
