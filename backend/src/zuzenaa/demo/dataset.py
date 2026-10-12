"""El mundo ficticio del modo demo (única fuente de verdad; sin I/O).

Una organización (``ikastola-demo``) con una clase activa (``1-maila``), otra
archivada (``2-maila``), dos assignments (``p1``, ``p2``) y seis alumnos con
entregas en distintos estados: varias revisiones analizadas, revisiones
pendientes, una entrega sin analizar y una no aceptada (fila ``error``).

Los diccionarios *Fixture* tienen la forma exacta que devuelve ``gh``: el runner
demo los serializa con ``json.dumps`` y los valida ``github/models.py``, como
con el CLI real. Los proyectos de los alumnos se describen como una secuencia
de commits (deltas acumulativos de ficheros) para que el seed fabrique repos
git con historia real y el agente pueda calcular diffs entre revisiones.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import TypedDict

from zuzenaa.github.results import TestCaseResult, TestResults

DEMO_ORG = "ikastola-demo"
DEMO_ORG_DESCRIPTION = "Ikastola de prueba · datos ficticios de ZuzenAA"
ACTIVE_CLASSROOM = "1-maila"
ARCHIVED_CLASSROOM = "2-maila"
ASSIGNMENT_P1 = "p1"
ASSIGNMENT_P2 = "p2"
TEMPLATE_REPO = "template-python"


class TeamFixture(TypedDict):
    id: int
    slug: str


class ClassroomFixture(TypedDict):
    short_name: str
    name: str
    term: str
    active: bool
    team: TeamFixture


class TestFixture(TypedDict):
    name: str
    type: str
    points: int


class TemplateFixture(TypedDict):
    owner: str
    repo: str
    branch: str


class AssignmentFixture(TypedDict):
    slug: str
    name: str
    description: str
    mode: str
    autograder: str
    template: TemplateFixture
    tests: list[TestFixture]
    feedback_pr: bool
    due: str
    available_from: str
    locked: bool
    closed: bool


class StudentFixture(TypedDict):
    username: str
    first_name: str
    last_name: str
    email: str
    section: str
    github_id: int


class StaffFixture(TypedDict):
    username: str
    role: str


class CommitFixture(TypedDict):
    message: str
    files: dict[str, str]  # ficheros añadidos/modificados en este commit (delta)
    day_offset: int  # días antes de "hoy"
    hour: int  # hora UTC


@dataclass(frozen=True)
class SubmissionSpec:
    """Cómo entrega un alumno un assignment.

    ``commit_count`` commits del track del assignment; los ``analyze_count``
    primeros se analizan en el seed (el resto quedan para «Analizar» en vivo).
    ``day_offsets`` (uno por commit) deben ser estrictamente decrecientes: así
    las fechas de commit, y con ellas las de los análisis, crecen en el tiempo.
    """

    commit_count: int
    analyze_count: int
    day_offsets: tuple[int, ...]


@dataclass(frozen=True)
class DemoState:
    org: str
    classrooms: tuple[ClassroomFixture, ...]
    assignments: dict[str, tuple[AssignmentFixture, ...]]  # clase -> assignments
    students: tuple[StudentFixture, ...]  # alumnado de la clase activa
    staff: tuple[StaffFixture, ...]


CLASSROOMS: tuple[ClassroomFixture, ...] = (
    {
        "short_name": ACTIVE_CLASSROOM,
        "name": "1. maila · Programazioa I",
        "term": "2025-2026",
        "active": True,
        "team": {"id": 101, "slug": f"classroom50-{ACTIVE_CLASSROOM}"},
    },
    {
        "short_name": ARCHIVED_CLASSROOM,
        "name": "2. maila · Programazioa II",
        "term": "2024-2025",
        "active": False,
        "team": {"id": 102, "slug": f"classroom50-{ARCHIVED_CLASSROOM}"},
    },
)

STUDENTS: tuple[StudentFixture, ...] = (
    {
        "username": "ane-urrutia",
        "first_name": "Ane",
        "last_name": "Urrutia",
        "email": "ane.urrutia@ikastola-demo.test",
        "section": "A",
        "github_id": 900001,
    },
    {
        "username": "unai-zabala",
        "first_name": "Unai",
        "last_name": "Zabala",
        "email": "unai.zabala@ikastola-demo.test",
        "section": "A",
        "github_id": 900002,
    },
    {
        "username": "maialen-ortiz",
        "first_name": "Maialen",
        "last_name": "Ortiz",
        "email": "maialen.ortiz@ikastola-demo.test",
        "section": "B",
        "github_id": 900003,
    },
    {
        "username": "jone-larrea",
        "first_name": "Jone",
        "last_name": "Larrea",
        "email": "jone.larrea@ikastola-demo.test",
        "section": "B",
        "github_id": 900004,
    },
    {
        "username": "ekain-agirre",
        "first_name": "Ekain",
        "last_name": "Agirre",
        "email": "ekain.agirre@ikastola-demo.test",
        "section": "B",
        "github_id": 900005,
    },
    {
        "username": "nerea-mendia",
        "first_name": "Nerea",
        "last_name": "Mendia",
        "email": "nerea.mendia@ikastola-demo.test",
        "section": "A",
        "github_id": 900006,
    },
)

STAFF: tuple[StaffFixture, ...] = (
    {"username": "irakasle-miren", "role": "instructor"},
    {"username": "praktikante-urtzi", "role": "ta"},
)

# Matriz de entregas: assignment -> login -> spec. Quien no aparece en p2 (Maialen)
# no aceptó la entrega: su clon falla y queda una fila ``error``, como en la vida real.
SUBMISSIONS: dict[str, dict[str, SubmissionSpec]] = {
    ASSIGNMENT_P1: {
        "ane-urrutia": SubmissionSpec(4, 3, (20, 13, 6, 2)),  # queda c4 por analizar
        "unai-zabala": SubmissionSpec(3, 3, (19, 11, 4)),
        "maialen-ortiz": SubmissionSpec(3, 2, (21, 10, 3)),  # queda c3 por analizar
        "jone-larrea": SubmissionSpec(2, 0, (14, 5)),  # sin analizar (estado vacío)
        "ekain-agirre": SubmissionSpec(2, 1, (16, 7)),
        "nerea-mendia": SubmissionSpec(3, 3, (18, 12, 5)),
    },
    ASSIGNMENT_P2: {
        "ane-urrutia": SubmissionSpec(3, 2, (29, 22, 9)),
        "unai-zabala": SubmissionSpec(2, 2, (27, 12)),
        "jone-larrea": SubmissionSpec(2, 1, (26, 8)),
        "ekain-agirre": SubmissionSpec(2, 0, (25, 6)),  # sin analizar (estado vacío)
        "nerea-mendia": SubmissionSpec(2, 2, (28, 10)),
    },
}

# Entrega del login real que se inyecta (para la superficie alumno «Mis clases»).
INJECTED_SUBMISSIONS: dict[str, SubmissionSpec] = {
    ASSIGNMENT_P1: SubmissionSpec(3, 3, (17, 9, 3)),
}

_AUTHOR_TOKEN = "__AUTHOR__"
_HOURS = (10, 16, 19, 12, 21)

# --- Track p1: "Batuketa-kalkulagailua" -------------------------------------------

_P1_C1_MAIN = '''# Batuketa-kalkulagailua
# Egilea: __AUTHOR__


def batu(a, b):
    return a + b


def main():
    # TODO: onartu zenbaki hamartarrak
    a = int(input("Lehen zenbakia: "))
    b = int(input("Bigarren zenbakia: "))
    print("Emaitza:", batu(a, b))


if __name__ == "__main__":
    main()
'''

_P1_C2_MAIN = '''# Batuketa-kalkulagailua
# Egilea: __AUTHOR__


def batu(a, b):
    return a + b


def irakurri(mezua):
    testua = input(mezua)
    try:
        return float(testua)
    except ValueError:
        print("Ez da zenbaki bat:", testua)
        return None


def main():
    a = irakurri("Lehen zenbakia: ")
    b = irakurri("Bigarren zenbakia: ")
    if a is None or b is None:
        return
    print("Emaitza:", batu(a, b))


if __name__ == "__main__":
    main()
'''

_P1_README = """# Batuketa-kalkulagailua

Egilea: __AUTHOR__

Bi zenbaki irakurri eta haien batura erakusten du.

## Nola exekutatu

```sh
python kalkulagailua.py
```
"""

_P1_C3_MAIN = '''"""Batuketa-kalkulagailua.

Egilea: __AUTHOR__
"""


def batu(a, b):
    """Itzuli a eta b-ren batura."""
    return a + b


def irakurri_zenbakia(mezua):
    """Irakurri zenbaki bat teklatutik; baliogabea bada, None."""
    testua = input(mezua)
    try:
        return float(testua)
    except ValueError:
        print("Ez da zenbaki bat:", testua)
        return None


def main():
    a = irakurri_zenbakia("Lehen zenbakia: ")
    b = irakurri_zenbakia("Bigarren zenbakia: ")
    if a is None or b is None:
        return
    print("Emaitza:", batu(a, b))


if __name__ == "__main__":
    main()
'''

_P1_C3_TESTS = '''from kalkulagailua import batu


def test_batu_osoak():
    assert batu(2, 3) == 5


def test_batu_negatiboak():
    assert batu(-2, 3) == 1


def test_batu_hamartarrak():
    assert batu(0.5, 0.25) == 0.75
'''

_P1_C4_MAIN = '''"""Batuketa-kalkulagailua: bi zenbaki batu komando-lerrotik.

Egilea: __AUTHOR__
"""

import argparse


def batu(a, b):
    """Itzuli a eta b-ren batura."""
    return a + b


def bihurtu_zenbakia(testua):
    """Bihurtu testua zenbaki; baliogabea bada, None."""
    try:
        return float(testua)
    except ValueError:
        return None


def main(argv=None):
    parser = argparse.ArgumentParser(description="Bi zenbaki batu.")
    parser.add_argument("a")
    parser.add_argument("b")
    args = parser.parse_args(argv)
    a = bihurtu_zenbakia(args.a)
    b = bihurtu_zenbakia(args.b)
    if a is None or b is None:
        print("Sarrera okerra: zenbakiak behar dira.")
        return 1
    print("Emaitza:", batu(a, b))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''

_P1_C4_TESTS = '''from kalkulagailua import batu, bihurtu_zenbakia, main


def test_batu_osoak():
    assert batu(2, 3) == 5


def test_batu_negatiboak():
    assert batu(-2, 3) == 1


def test_batu_hamartarrak():
    assert batu(0.5, 0.25) == 0.75


def test_bihurtu_negatiboa():
    assert bihurtu_zenbakia("-3") == -3.0


def test_bihurtu_okerra():
    assert bihurtu_zenbakia("abc") is None


def test_main_sarrera_okerra():
    assert main(["1", "x"]) == 1
'''

_P1_TRACK: tuple[tuple[str, dict[str, str]], ...] = (
    ("Lehen bertsioa: batu funtzioa", {"kalkulagailua.py": _P1_C1_MAIN}),
    (
        "README gehitu eta sarrera balidatu",
        {"kalkulagailua.py": _P1_C2_MAIN, "README.md": _P1_README},
    ),
    (
        "Probak gehitu (pytest)",
        {"kalkulagailua.py": _P1_C3_MAIN, "tests/test_kalkulagailua.py": _P1_C3_TESTS},
    ),
    (
        "Zenbaki negatiboak eta argparse",
        {"kalkulagailua.py": _P1_C4_MAIN, "tests/test_kalkulagailua.py": _P1_C4_TESTS},
    ),
)

# --- Track p2: "Zerrenden estatistikak" -------------------------------------------

_P2_C1_MAIN = '''# Zerrenden estatistikak
# Egilea: __AUTHOR__


def batez_bestekoa(zenbakiak):
    # TODO: zer gertatzen da zerrenda hutsarekin?
    return sum(zenbakiak) / len(zenbakiak)


def main():
    datuak = [4, 8, 15, 16, 23, 42]
    print("Batez bestekoa:", batez_bestekoa(datuak))


if __name__ == "__main__":
    main()
'''

_P2_C2_MAIN = '''# Zerrenden estatistikak
# Egilea: __AUTHOR__


def batez_bestekoa(zenbakiak):
    if not zenbakiak:
        return None
    return sum(zenbakiak) / len(zenbakiak)


def handiena(zenbakiak):
    if not zenbakiak:
        return None
    return max(zenbakiak)


def txikiena(zenbakiak):
    if not zenbakiak:
        return None
    return min(zenbakiak)


def main():
    datuak = [4, 8, 15, 16, 23, 42]
    print("Batez bestekoa:", batez_bestekoa(datuak))
    print("Handiena:", handiena(datuak))
    print("Txikiena:", txikiena(datuak))


if __name__ == "__main__":
    main()
'''

_P2_README = """# Zerrenden estatistikak

Egilea: __AUTHOR__

Zenbaki-zerrenda baten batez bestekoa, handiena eta txikiena kalkulatzen ditu.

## Nola exekutatu

```sh
python estatistikak.py
```
"""

_P2_C3_MAIN = '''"""Zerrenden estatistikak.

Egilea: __AUTHOR__
"""


def batez_bestekoa(zenbakiak):
    """Batez besteko aritmetikoa; zerrenda hutsarekin None."""
    if not zenbakiak:
        return None
    return sum(zenbakiak) / len(zenbakiak)


def handiena(zenbakiak):
    if not zenbakiak:
        return None
    return max(zenbakiak)


def txikiena(zenbakiak):
    if not zenbakiak:
        return None
    return min(zenbakiak)


def mediana(zenbakiak):
    """Mediana; zerrenda hutsarekin None."""
    if not zenbakiak:
        return None
    ordenatuta = sorted(zenbakiak)
    erdia = len(ordenatuta) // 2
    if len(ordenatuta) % 2 == 1:
        return ordenatuta[erdia]
    return (ordenatuta[erdia - 1] + ordenatuta[erdia]) / 2


def main():
    datuak = [4, 8, 15, 16, 23, 42]
    print("Batez bestekoa:", batez_bestekoa(datuak))
    print("Mediana:", mediana(datuak))
    print("Handiena:", handiena(datuak))
    print("Txikiena:", txikiena(datuak))


if __name__ == "__main__":
    main()
'''

_P2_C3_TESTS = '''import pytest

from estatistikak import batez_bestekoa, handiena, mediana, txikiena


def test_batez_bestekoa():
    assert batez_bestekoa([1, 2, 3, 4]) == pytest.approx(2.5)


def test_batez_bestekoa_hutsa():
    assert batez_bestekoa([]) is None


def test_mediana_bakoitia():
    assert mediana([3, 1, 2]) == 2


def test_mediana_bikoitia():
    assert mediana([1, 2, 3, 4]) == pytest.approx(2.5)


def test_muturrak():
    assert handiena([4, 8, 15]) == 15
    assert txikiena([4, 8, 15]) == 4
'''

_P2_TRACK: tuple[tuple[str, dict[str, str]], ...] = (
    ("Lehen bertsioa: batez bestekoa", {"estatistikak.py": _P2_C1_MAIN}),
    (
        "Zeroz zatitzea saihestu eta README",
        {"estatistikak.py": _P2_C2_MAIN, "README.md": _P2_README},
    ),
    (
        "Probak eta mediana",
        {"estatistikak.py": _P2_C3_MAIN, "tests/test_estatistikak.py": _P2_C3_TESTS},
    ),
)

TRACKS: dict[str, tuple[tuple[str, dict[str, str]], ...]] = {
    ASSIGNMENT_P1: _P1_TRACK,
    ASSIGNMENT_P2: _P2_TRACK,
}

# --- Tests de Classroom 50 (los que corren en GitHub Actions) ----------------------

TESTS: dict[str, list[TestFixture]] = {
    ASSIGNMENT_P1: [
        {"name": "test_batu", "type": "pytest", "points": 10},
        {"name": "test_sarrera_okerra", "type": "pytest", "points": 5},
    ],
    ASSIGNMENT_P2: [
        {"name": "test_batez_bestekoa", "type": "pytest", "points": 10},
        {"name": "test_mediana", "type": "pytest", "points": 10},
    ],
}

# Tests que pasan en cada commit del track (alineado con ``TRACKS``). Refleja el
# código: en p1 el primer commit revienta con una entrada no numérica; en p2 la
# media falla con la lista vacía hasta el commit 2 y la mediana llega en el 3.
TRACK_PASSING: dict[str, tuple[frozenset[str], ...]] = {
    ASSIGNMENT_P1: (
        frozenset({"test_batu"}),
        frozenset({"test_batu", "test_sarrera_okerra"}),
        frozenset({"test_batu", "test_sarrera_okerra"}),
        frozenset({"test_batu", "test_sarrera_okerra"}),
    ),
    ASSIGNMENT_P2: (
        frozenset(),
        frozenset({"test_batez_bestekoa"}),
        frozenset({"test_batez_bestekoa", "test_mediana"}),
    ),
}


def commit_results(assignment: str, index: int, commit_sha: str) -> TestResults:
    """El ``result.json`` que publicaría Classroom 50 para el commit ``index`` del track."""
    passing = TRACK_PASSING[assignment][index]
    tests = [
        TestCaseResult(
            name=test["name"],
            passed=test["name"] in passing,
            points=test["points"] if test["name"] in passing else 0,
            max_points=test["points"],
        )
        for test in TESTS[assignment]
    ]
    return TestResults(
        commit=commit_sha,
        score=sum(test.points for test in tests),
        max_score=sum(test.max_points for test in tests),
        tests=tests,
    )


def _iso(day: date) -> str:
    return day.isoformat()


def build_assignments(today: date) -> tuple[AssignmentFixture, ...]:
    template: TemplateFixture = {"owner": DEMO_ORG, "repo": TEMPLATE_REPO, "branch": "main"}
    return (
        {
            "slug": ASSIGNMENT_P1,
            "name": "Batuketa-kalkulagailua",
            "description": "Bi zenbaki irakurri eta batu; sarrera okerrak kontrolatu.",
            "mode": "individual",
            "autograder": "default",
            "template": template,
            "tests": list(TESTS[ASSIGNMENT_P1]),
            "feedback_pr": False,
            "due": _iso(today + timedelta(days=1)),  # abierta: quedan revisiones por analizar
            "available_from": _iso(today - timedelta(days=24)),
            "locked": False,
            "closed": False,
        },
        {
            "slug": ASSIGNMENT_P2,
            "name": "Zerrenden estatistikak",
            "description": "Zerrenda baten batez bestekoa, mediana eta muturrak.",
            "mode": "individual",
            "autograder": "default",
            "template": template,
            "tests": list(TESTS[ASSIGNMENT_P2]),
            "feedback_pr": False,
            "due": _iso(today - timedelta(days=3)),  # cerrada
            "available_from": _iso(today - timedelta(days=31)),
            "locked": False,
            "closed": True,
        },
    )


def default_state(today: date | None = None) -> DemoState:
    """El estado ficticio completo (las fechas de los assignments son relativas a hoy)."""
    day = today or datetime.now(UTC).date()
    return DemoState(
        org=DEMO_ORG,
        classrooms=CLASSROOMS,
        assignments={ACTIVE_CLASSROOM: build_assignments(day), ARCHIVED_CLASSROOM: ()},
        students=STUDENTS,
        staff=STAFF,
    )


def students_of(state: DemoState, classroom: str) -> list[StudentFixture]:
    """Alumnado de una clase: solo la activa tiene; la archivada está vacía."""
    return list(state.students) if classroom == ACTIVE_CLASSROOM else []


def roster_csv(state: DemoState, classroom: str) -> str:
    """El ``roster.csv`` que Classroom 50 guarda en ``<org>/classroom50``."""
    fields = ["username", "first_name", "last_name", "email", "section", "github_id"]
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for student in students_of(state, classroom):
        writer.writerow(dict(student))  # las claves del fixture son exactamente las columnas
    return buffer.getvalue()


def display_name(login: str, name: str | None) -> str:
    """Nombre con el que firma los commits (el real si lo hay; si no, el login)."""
    cleaned = (name or "").strip()
    return cleaned or login


def student_display_name(student: StudentFixture) -> str:
    return f"{student['first_name']} {student['last_name']}"


def commit_datetime(today: date, day_offset: int, hour: int) -> datetime:
    """Fecha UTC de un commit: ``day_offset`` días antes de hoy, a las ``hour``."""
    return datetime.combine(today - timedelta(days=day_offset), time(hour=hour), tzinfo=UTC)


def build_commits(assignment: str, spec: SubmissionSpec, *, author: str) -> list[CommitFixture]:
    """Los commits concretos de una entrega: track del assignment, firmados por ``author``."""
    track = TRACKS[assignment]
    if spec.commit_count > len(track):
        raise ValueError(f"{assignment}: el track solo tiene {len(track)} commits")
    if len(spec.day_offsets) != spec.commit_count:
        raise ValueError(f"{assignment}: hace falta un day_offset por commit")
    commits: list[CommitFixture] = []
    for index in range(spec.commit_count):
        message, files = track_commit(assignment, index, author=author)
        commits.append(
            {
                "message": message,
                "files": files,
                "day_offset": spec.day_offsets[index],
                "hour": _HOURS[index % len(_HOURS)],
            }
        )
    return commits


def track_commit(assignment: str, index: int, *, author: str) -> tuple[str, dict[str, str]]:
    """Mensaje y ficheros (delta) del commit ``index`` del track, firmados por ``author``."""
    message, files = TRACKS[assignment][index]
    signed = {path: content.replace(_AUTHOR_TOKEN, author) for path, content in files.items()}
    return message, signed


def cumulative_tree(commits: list[CommitFixture], upto: int) -> dict[str, str]:
    """Estado del árbol tras aplicar los ``upto`` primeros commits (deltas acumulados)."""
    tree: dict[str, str] = {}
    for commit in commits[:upto]:
        tree.update(commit["files"])
    return tree


__all__ = [
    "ACTIVE_CLASSROOM",
    "ARCHIVED_CLASSROOM",
    "ASSIGNMENT_P1",
    "ASSIGNMENT_P2",
    "CLASSROOMS",
    "DEMO_ORG",
    "DEMO_ORG_DESCRIPTION",
    "INJECTED_SUBMISSIONS",
    "STAFF",
    "STUDENTS",
    "SUBMISSIONS",
    "TESTS",
    "TRACKS",
    "TRACK_PASSING",
    "AssignmentFixture",
    "ClassroomFixture",
    "CommitFixture",
    "DemoState",
    "StaffFixture",
    "StudentFixture",
    "SubmissionSpec",
    "build_assignments",
    "build_commits",
    "commit_datetime",
    "commit_results",
    "cumulative_tree",
    "default_state",
    "display_name",
    "roster_csv",
    "student_display_name",
    "students_of",
    "track_commit",
]
