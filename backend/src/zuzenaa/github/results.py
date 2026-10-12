"""Resultados de los tests de Classroom 50 por commit (solo lectura).

Los tests corren en GitHub Actions: cada push publica una Release con un
``result.json``. ZuzenAA **no** re-ejecuta los tests; solo lee ese resultado para
que el agente pueda comentarlo junto al código.

Hoy solo existe el lector del modo demo (releases ficticias en disco). El lector
real queda pendiente de verificar el formato exacto del ``result.json`` de
Classroom 50; mientras tanto devuelve ``None`` y el análisis sigue sin tests.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from zuzenaa.config import settings


@dataclass
class TestCaseResult:
    __test__ = False  # no es un test de pytest

    name: str
    passed: bool
    points: int
    max_points: int


@dataclass
class TestResults:
    __test__ = False  # no es un test de pytest

    commit: str
    score: int
    max_score: int
    tests: list[TestCaseResult]

    @property
    def passed(self) -> int:
        return sum(1 for test in self.tests if test.passed)

    @property
    def failing(self) -> list[str]:
        return [test.name for test in self.tests if not test.passed]

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["passed"] = self.passed
        data["total"] = len(self.tests)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> TestResults:
        raw_tests = data.get("tests")
        tests = [
            TestCaseResult(
                name=str(item["name"]),
                passed=bool(item["passed"]),
                points=int(item["points"]),
                max_points=int(item["max_points"]),
            )
            for item in (raw_tests if isinstance(raw_tests, list) else [])
            if isinstance(item, dict)
        ]
        return cls(
            commit=str(data.get("commit", "")),
            score=int(str(data.get("score", 0))),
            max_score=int(str(data.get("max_score", 0))),
            tests=tests,
        )


async def load_test_results(
    *, org: str, repo_full_name: str, commit_sha: str
) -> TestResults | None:
    """Resultado de los tests de ``commit_sha``, o ``None`` si no hay."""
    if settings.demo_mode:
        from zuzenaa.demo import releases

        return releases.read(org, repo_full_name, commit_sha)
    return None


__all__ = ["TestCaseResult", "TestResults", "load_test_results"]
