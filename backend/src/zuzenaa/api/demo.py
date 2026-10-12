"""Endpoints del modo demo (solo con ``ZUZENAA_DEMO_MODE=true``; si no, 404).

Ver ``docs/06-datos-de-prueba.md``. Nunca en producción.
"""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from zuzenaa.api.analyses import AnalyzeOutcomeOut, TestResultsOut, authorize_staff
from zuzenaa.api.deps import GhCliDep, OptionalUserDep
from zuzenaa.config import settings

router = APIRouter(prefix="/demo", tags=["demo"])


class PushOut(BaseModel):
    owner: str
    assignment: str
    commit_sha: str
    message: str
    tests: TestResultsOut
    analysis: AnalyzeOutcomeOut


@router.post(
    "/orgs/{org}/classrooms/{classroom}/assignments/{assignment}/repos/{owner}/push",
    response_model=PushOut,
)
async def simulate_push(
    org: str, classroom: str, assignment: str, owner: str, user: OptionalUserDep, gh: GhCliDep
) -> PushOut:
    """Simula que ``owner`` sube su siguiente revisión: tests, descarga y análisis."""
    if not settings.demo_mode:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Found")
    # Simula el push de un alumno: es una herramienta del profesorado.
    await authorize_staff(
        org=org,
        classroom=classroom,
        user=user,
        gh=gh,
        denied="Solo el profesorado puede simular pushes.",
    )

    from zuzenaa.demo import dataset
    from zuzenaa.demo.push import PushError
    from zuzenaa.demo.push import simulate_push as run_push

    if (org, classroom) != (dataset.DEMO_ORG, dataset.ACTIVE_CLASSROOM):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El push simulado solo existe en la clase activa de la demo.",
        )
    try:
        outcome = await run_push(assignment=assignment, owner=owner)
    except PushError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    analysis = outcome.analysis
    return PushOut(
        owner=outcome.owner,
        assignment=outcome.assignment,
        commit_sha=outcome.commit_sha,
        message=outcome.message,
        tests=TestResultsOut.model_validate(outcome.tests.to_dict()),
        analysis=AnalyzeOutcomeOut(
            owner=analysis.owner,
            status=analysis.status,
            commit_sha=analysis.commit_sha,
            analysis_id=analysis.analysis_id,
            reason=analysis.reason,
        ),
    )
