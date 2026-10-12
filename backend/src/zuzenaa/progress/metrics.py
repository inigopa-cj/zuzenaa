"""Métricas de evolución: progreso del alumno y evolución de la clase.

Funciones puras (sin BD ni disco) sobre lo que ZuzenAA ya guarda:

- los **análisis** de cada commit (fecha, feedback estructurado y resultado de tests);
- la **historia git** del clon (``repos.git.log``), que incluye también los commits
  que nunca se analizaron.

La evolución de la clase **no se calcula aparte**: agrega el progreso de cada
alumno, así ambos elementos cuentan siempre lo mismo. Los resúmenes son plantillas
deterministas (el «mock»): orientan sin dar la solución.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from zuzenaa.repos.git import CommitInfo

DAY = 86_400
STALE_DAYS = 7  # días sin commits (con tests pendientes) para avisar
HINT_STREAK_ALERT = 3  # misma pista en N revisiones seguidas
MAX_TIMELINE_DAYS = 60


@dataclass
class AnalysisRecord:
    """Lo que el progreso necesita de una fila ``analyses``."""

    commit_sha: str
    at: int  # fecha del commit (o del análisis si no se conoce)
    payload: dict[str, object]  # feedback_json ya parseado


@dataclass
class TestPoint:
    __test__ = False  # no es un test de pytest

    commit: str
    at: int
    passed: int
    total: int
    score: int
    max_score: int

    @property
    def ratio(self) -> float:
        return self.score / self.max_score if self.max_score else 0.0


@dataclass
class TestStatus:
    __test__ = False  # no es un test de pytest

    name: str
    passing: bool  # en la última revisión con tests
    first_passed_commit: str | None
    first_passed_at: int | None
    regressions: int  # veces que pasó y luego dejó de pasar


@dataclass
class Regression:
    test: str
    commit: str  # revisión en la que dejó de pasar
    at: int


@dataclass
class Rhythm:
    commits: int
    analysed_commits: int
    first_at: int
    last_at: int
    active_days: int
    days_since_last: int
    avg_lines: int
    largest_lines: int
    largest_commit: str


@dataclass
class Alert:
    kind: str  # sin_analisis | regresion | pista_repetida | sin_avance
    text: str


@dataclass
class StudentProgress:
    owner: str
    analyses: int
    current: TestPoint | None
    timeline: list[TestPoint]
    tests: list[TestStatus]
    regressions: list[Regression]
    hint_streak: int
    repeated_hint: str | None
    rhythm: Rhythm | None
    alerts: list[Alert]
    summary: str
    latest_hint: str | None = None


@dataclass
class TestPassRate:
    __test__ = False  # no es un test de pytest

    name: str
    passing: int
    students: int

    @property
    def rate(self) -> float:
        return self.passing / self.students if self.students else 0.0


@dataclass
class DayPoint:
    day: str  # YYYY-MM-DD (UTC)
    avg_ratio: float  # media de puntos/máximo de quien ya tenía resultado
    students: int


@dataclass
class StudentRow:
    owner: str
    analyses: int
    passed: int | None
    total: int | None
    score: int | None
    max_score: int | None
    last_commit_at: int | None
    alerts: list[str]


@dataclass
class HintCount:
    text: str
    students: int


@dataclass
class ClassEvolution:
    students: int
    analysed: int
    with_tests: int  # entregas con resultado de tests en su último análisis
    all_passing: int
    avg_ratio: float | None
    tests: list[TestPassRate]
    timeline: list[DayPoint]
    attention: list[StudentRow]
    rows: list[StudentRow]
    common_hints: list[HintCount] = field(default_factory=list)
    summary: str = ""


# --- Progreso del alumno ----------------------------------------------------------


def _dedupe(records: list[AnalysisRecord]) -> list[AnalysisRecord]:
    """Un registro por commit (el último: un reanálisis sustituye al anterior)."""
    by_commit: dict[str, AnalysisRecord] = {}
    for record in records:
        by_commit.pop(record.commit_sha, None)
        by_commit[record.commit_sha] = record
    return sorted(by_commit.values(), key=lambda r: r.at)


def _test_cases(payload: dict[str, object]) -> dict[str, bool] | None:
    tests = payload.get("tests")
    if not isinstance(tests, dict) or not isinstance(tests.get("tests"), list):
        return None
    cases: dict[str, bool] = {}
    for item in tests["tests"]:
        if isinstance(item, dict) and "name" in item:
            cases[str(item["name"])] = bool(item.get("passed"))
    return cases


def _point(record: AnalysisRecord) -> TestPoint | None:
    tests = record.payload.get("tests")
    cases = _test_cases(record.payload)
    if not isinstance(tests, dict) or cases is None:
        return None
    return TestPoint(
        commit=record.commit_sha,
        at=record.at,
        passed=sum(cases.values()),
        total=len(cases),
        score=_int(tests.get("score")),
        max_score=_int(tests.get("max_score")),
    )


def _int(value: object) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return 0


def _hint(payload: dict[str, object]) -> str | None:
    pista = payload.get("pista")
    if isinstance(pista, dict) and isinstance(pista.get("text"), str):
        return str(pista["text"])
    return None


def _rhythm(commits: list[CommitInfo], analysed: set[str], now: int) -> Rhythm | None:
    if not commits:
        return None
    sizes = [c.insertions + c.deletions for c in commits]
    largest = max(range(len(commits)), key=lambda i: sizes[i])
    days = {datetime.fromtimestamp(c.committed_at, UTC).date() for c in commits}
    last_at = max(c.committed_at for c in commits)
    return Rhythm(
        commits=len(commits),
        analysed_commits=sum(1 for c in commits if c.sha in analysed),
        first_at=min(c.committed_at for c in commits),
        last_at=last_at,
        active_days=len(days),
        days_since_last=max(0, (now - last_at) // DAY),
        avg_lines=round(sum(sizes) / len(sizes)),
        largest_lines=sizes[largest],
        largest_commit=commits[largest].sha,
    )


def student_progress(
    owner: str, records: list[AnalysisRecord], commits: list[CommitInfo], *, now: int
) -> StudentProgress:
    revisions = _dedupe(records)
    timeline = [point for point in (_point(r) for r in revisions) if point is not None]
    case_history = [
        (r, cases) for r in revisions if (cases := _test_cases(r.payload)) is not None
    ]

    # Tests: cuándo empezó a pasar cada uno y si se rompió después.
    regressions: list[Regression] = []
    statuses: dict[str, TestStatus] = {}
    previous: dict[str, bool] = {}
    for record, cases in case_history:
        for name, passed in cases.items():
            status = statuses.setdefault(name, TestStatus(name, passed, None, None, 0))
            status.passing = passed
            if passed and status.first_passed_commit is None:
                status.first_passed_commit = record.commit_sha
                status.first_passed_at = record.at
            if previous.get(name) and not passed:
                status.regressions += 1
                regressions.append(Regression(name, record.commit_sha, record.at))
        previous = cases

    # Pista repetida al final del histórico: el alumno no la está aplicando.
    hints = [_hint(r.payload) for r in revisions]
    latest_hint = hints[-1] if hints else None
    streak = 0
    for hint in reversed(hints):
        if hint is None or hint != latest_hint:
            break
        streak += 1

    rhythm = _rhythm(commits, {r.commit_sha for r in revisions}, now)
    current = timeline[-1] if timeline else None
    # Con todos los tests en verde, repetir la pista no indica un problema pendiente.
    all_green = current is not None and current.total > 0 and current.passed == current.total
    repeated = streak >= HINT_STREAK_ALERT and not all_green
    alerts = _alerts(revisions, current, regressions, streak if repeated else 0, rhythm)
    progress = StudentProgress(
        owner=owner,
        analyses=len(revisions),
        current=current,
        timeline=timeline,
        tests=list(statuses.values()),
        regressions=regressions,
        hint_streak=streak,
        repeated_hint=latest_hint if repeated else None,
        rhythm=rhythm,
        alerts=alerts,
        summary="",
        latest_hint=latest_hint,
    )
    progress.summary = _student_summary(progress)
    return progress


def _alerts(
    revisions: list[AnalysisRecord],
    current: TestPoint | None,
    regressions: list[Regression],
    streak: int,
    rhythm: Rhythm | None,
) -> list[Alert]:
    alerts: list[Alert] = []
    if not revisions:
        alerts.append(Alert("sin_analisis", "Todavía no hay ninguna revisión analizada."))
    if current is not None and any(r.commit == current.commit for r in regressions):
        broken = sorted({r.test for r in regressions if r.commit == current.commit})
        alerts.append(
            Alert("regresion", f"La última revisión rompe tests que pasaban: {', '.join(broken)}.")
        )
    if streak >= HINT_STREAK_ALERT:
        alerts.append(
            Alert("pista_repetida", f"La misma pista se repite en las últimas {streak} revisiones.")
        )
    pending = current is None or current.passed < current.total
    if rhythm is not None and pending and rhythm.days_since_last >= STALE_DAYS:
        alerts.append(
            Alert(
                "sin_avance",
                f"{rhythm.days_since_last} días sin commits y quedan tests por pasar.",
            )
        )
    return alerts


def _short(sha: str) -> str:
    return sha[:7]


def _student_summary(p: StudentProgress) -> str:
    parts: list[str] = []
    if p.rhythm is not None:
        r = p.rhythm
        parts.append(
            f"Llevas {r.commits} commit(s) en {r.active_days} día(s) con actividad "
            f"({r.analysed_commits} analizado(s))."
        )
    if not p.analyses:
        parts.append("Todavía no hay revisiones analizadas: el progreso aparecerá con la primera.")
        return " ".join(parts)

    if p.current is not None:
        first = p.timeline[0]
        if p.current.passed == p.current.total and p.current.total:
            since = next(
                (pt for pt in p.timeline if pt.total and pt.passed == pt.total), p.current
            )
            parts.append(
                f"Todos los tests pasan ({p.current.score}/{p.current.max_score} puntos) "
                f"desde la revisión {_short(since.commit)}."
            )
        else:
            parts.append(
                f"Ahora pasan {p.current.passed} de {p.current.total} tests "
                f"({p.current.score}/{p.current.max_score} puntos); empezaste con {first.passed}."
            )
            pending = [t.name for t in p.tests if not t.passing]
            if pending:
                parts.append(f"Te queda: {', '.join(pending)}.")
    if p.regressions:
        last = p.regressions[-1]
        parts.append(
            f"En la revisión {_short(last.commit)} dejó de pasar {last.test}: antes de subir, "
            "ejecuta los tests para no romper lo que ya funcionaba."
        )
    if p.repeated_hint is not None:
        parts.append(
            f"La misma pista se repite en las últimas {p.hint_streak} revisiones: "
            "vuelve a leerla con calma y prueba ese caso."
        )
    if p.rhythm is not None and p.rhythm.commits >= 2 and p.rhythm.largest_lines >= 3 * max(
        p.rhythm.avg_lines, 1
    ):
        parts.append(
            "Hay un commit mucho más grande que el resto: subir cambios pequeños hace más "
            "fácil encontrar qué se ha roto."
        )
    return " ".join(parts)


# --- Evolución de la clase --------------------------------------------------------


def _day(epoch: int) -> datetime:
    return datetime.fromtimestamp(epoch, UTC).replace(hour=0, minute=0, second=0, microsecond=0)


def _timeline(students: list[StudentProgress]) -> list[DayPoint]:
    """Media diaria de puntos de quien ya tenía resultado (último conocido ese día)."""
    points = [pt for s in students for pt in s.timeline]
    if not points:
        return []
    start = _day(min(pt.at for pt in points))
    end = _day(max(pt.at for pt in points))
    if (end - start).days >= MAX_TIMELINE_DAYS:
        start = end - timedelta(days=MAX_TIMELINE_DAYS - 1)

    out: list[DayPoint] = []
    day = start
    while day <= end:
        limit = int((day + timedelta(days=1)).timestamp())
        ratios = [
            known[-1].ratio
            for s in students
            if (known := [pt for pt in s.timeline if pt.at < limit])
        ]
        if ratios:
            out.append(
                DayPoint(
                    day=day.date().isoformat(),
                    avg_ratio=round(sum(ratios) / len(ratios), 3),
                    students=len(ratios),
                )
            )
        day += timedelta(days=1)
    return out


def class_evolution(students: list[StudentProgress]) -> ClassEvolution:
    rows = [
        StudentRow(
            owner=s.owner,
            analyses=s.analyses,
            passed=s.current.passed if s.current else None,
            total=s.current.total if s.current else None,
            score=s.current.score if s.current else None,
            max_score=s.current.max_score if s.current else None,
            last_commit_at=s.rhythm.last_at if s.rhythm else None,
            alerts=[a.kind for a in s.alerts],
        )
        for s in students
    ]

    rates: dict[str, TestPassRate] = {}
    for s in students:
        for test in s.tests:
            rate = rates.setdefault(test.name, TestPassRate(test.name, 0, 0))
            rate.students += 1
            rate.passing += int(test.passing)
    tests = sorted(rates.values(), key=lambda t: (t.rate, t.name))

    with_results = [s.current for s in students if s.current is not None]
    avg_ratio = (
        round(sum(pt.ratio for pt in with_results) / len(with_results), 3)
        if with_results
        else None
    )
    hint_counts = Counter(s.latest_hint for s in students if s.latest_hint)
    common = [HintCount(text, n) for text, n in hint_counts.most_common(3) if n >= 2]

    evolution = ClassEvolution(
        students=len(students),
        analysed=sum(1 for s in students if s.analyses),
        with_tests=len(with_results),
        all_passing=sum(1 for pt in with_results if pt.total and pt.passed == pt.total),
        avg_ratio=avg_ratio,
        tests=tests,
        timeline=_timeline(students),
        attention=[row for row in rows if row.alerts],
        rows=rows,
        common_hints=common,
    )
    evolution.summary = _class_summary(evolution)
    return evolution


def _class_summary(c: ClassEvolution) -> str:
    if not c.students:
        return "No hay entregas descargadas en este assignment."
    parts = [f"{c.analysed} de {c.students} entregas tienen al menos un análisis."]
    if c.avg_ratio is not None:
        parts.append(
            f"De las {c.with_tests} con resultado de tests, {c.all_passing} los pasan todos; "
            f"la media es del {round(c.avg_ratio * 100)} % de los puntos."
        )
    hardest = next((t for t in c.tests if t.rate < 1), None)
    if hardest is not None:
        parts.append(
            f"El test que más cuesta es {hardest.name}: lo pasa el {round(hardest.rate * 100)} % "
            "(puede merecer una explicación en clase)."
        )
    if c.attention:
        parts.append(f"{len(c.attention)} alumno(s) necesitan atención.")
    return " ".join(parts)


__all__ = [
    "AnalysisRecord",
    "ClassEvolution",
    "StudentProgress",
    "class_evolution",
    "student_progress",
]
