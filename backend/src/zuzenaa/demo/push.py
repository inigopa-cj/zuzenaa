"""Push simulado: un alumno sube su siguiente revisión y ZuzenAA la analiza sola.

Reproduce en local el ciclo de un push en Classroom 50:

1. El alumno hace **commit + push** de la siguiente revisión de su *track* (el código
   con el que intenta pasar los tests) al origen git local.
2. «GitHub Actions» corre los tests y publica la **release** con ``result.json``
   (``demo/releases.py``). ZuzenAA no ejecuta nada: solo lo lee después.
3. ZuzenAA **descarga** el repo (``repos.service.sync_assignment``) y lo **analiza**
   (``agent.service.analyze_repository``), que lee ese resultado de tests.

Desde la web: botón «Simular push» (solo con ``ZUZENAA_DEMO_MODE=true``). Desde la
terminal: ``python -m zuzenaa.demo.push <assignment> <alumno>``.
"""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime

from zuzenaa.agent import service as agent_service
from zuzenaa.agent.service import AnalyzeOutcome
from zuzenaa.db.session import init_models
from zuzenaa.demo import clone_url_template, dataset, origins_root, releases, seed
from zuzenaa.github.results import TestResults
from zuzenaa.repos import paths


class PushError(RuntimeError):
    """El push no se puede simular (entrega no aceptada, track agotado...)."""


@dataclass
class PushOutcome:
    owner: str
    assignment: str
    commit_sha: str
    message: str
    tests: TestResults
    analysis: AnalyzeOutcome


async def simulate_push(*, assignment: str, owner: str) -> PushOutcome:
    org = dataset.DEMO_ORG
    classroom = dataset.ACTIVE_CLASSROOM
    if assignment not in dataset.TRACKS:
        raise PushError(f"assignment desconocido en la demo: {assignment!r}")

    full_name = paths.repo_full_name(org, classroom, assignment, owner)
    origin = origins_root() / org / full_name
    if not (origin / ".git").is_dir():
        raise PushError(
            f"{owner} no tiene repo para {assignment} (no aceptó la entrega o falta el seed)."
        )

    # 1. Commit + push de la siguiente revisión del track.
    index = len(seed.commit_shas(origin))
    if index >= len(dataset.TRACKS[assignment]):
        raise PushError(f"{owner} ya ha subido todas las revisiones de {assignment}.")
    message, files = dataset.track_commit(assignment, index, author=owner)
    sha = seed.commit_files(origin, files, message=message, when=datetime.now(UTC))

    # 2. Classroom 50 corre los tests en Actions y publica la release.
    tests = dataset.commit_results(assignment, index, sha)
    releases.write(org, full_name, tests)

    # 3. ZuzenAA reacciona al push: descarga y analiza (mismo camino que «Analizar»).
    [analysis] = await agent_service.sync_and_analyze(
        org=org,
        classroom=classroom,
        assignment=assignment,
        owners=[owner],
        token="demo",
        clone_url_template=clone_url_template(),
    )

    return PushOutcome(
        owner=owner,
        assignment=assignment,
        commit_sha=sha,
        message=message,
        tests=tests,
        analysis=analysis,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Simula el push de un alumno en el modo demo.")
    parser.add_argument("assignment", help="p. ej. p1")
    parser.add_argument("owner", help="login del alumno, p. ej. jone-larrea")
    args = parser.parse_args()

    async def run() -> PushOutcome:
        await init_models()
        return await simulate_push(assignment=args.assignment, owner=args.owner)

    try:
        outcome = asyncio.run(run())
    except PushError as exc:
        raise SystemExit(f"No se puede simular el push: {exc}") from exc
    print(
        f"Push de {outcome.owner} en {outcome.assignment}: {outcome.commit_sha[:7]} "
        f"«{outcome.message}» · tests {outcome.tests.passed}/{len(outcome.tests.tests)} "
        f"({outcome.tests.score}/{outcome.tests.max_score} puntos) · "
        f"análisis {outcome.analysis.status}"
    )


if __name__ == "__main__":
    main()
