"""Progreso del alumno y evolución de la clase (sobre el histórico ya guardado)."""

from fastapi import APIRouter, HTTPException, status

from zuzenaa.api.analyses import _authorize_owner, authorize_staff
from zuzenaa.api.deps import GhCliDep, OptionalUserDep
from zuzenaa.progress import service
from zuzenaa.progress.metrics import ClassEvolution, StudentProgress

router = APIRouter(
    prefix="/orgs/{org}/classrooms/{classroom}/assignments/{assignment}",
    tags=["progress"],
)


@router.get("/repos/{owner}/progress", response_model=StudentProgress)
async def student_progress(
    org: str,
    classroom: str,
    assignment: str,
    owner: str,
    user: OptionalUserDep,
    gh: GhCliDep,
) -> StudentProgress:
    """Progreso de una entrega: el propio alumno o el staff de la clase."""
    await _authorize_owner(org=org, classroom=classroom, owner=owner, user=user, gh=gh)
    repos = await service.repositories(org, classroom, assignment, owner)
    if not repos:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="repo no encontrado")
    return await service.progress_for(repos[0])


@router.get("/progress", response_model=ClassEvolution)
async def class_progress(
    org: str,
    classroom: str,
    assignment: str,
    user: OptionalUserDep,
    gh: GhCliDep,
) -> ClassEvolution:
    """Evolución de la clase: solo staff (agrega datos de todo el alumnado)."""
    await authorize_staff(
        org=org,
        classroom=classroom,
        user=user,
        gh=gh,
        denied="Solo el profesorado de la clase puede ver la evolución del grupo.",
    )
    return await service.class_progress(org, classroom, assignment)
