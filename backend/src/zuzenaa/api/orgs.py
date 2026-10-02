"""Read-only view of Classroom 50: orgs, classrooms, assignments, roster, templates."""

from fastapi import APIRouter, HTTPException, status

from zuzenaa.api.deps import GhCliDep
from zuzenaa.github.cli import GhError
from zuzenaa.github.models import (
    Assignment,
    Classroom,
    Org,
    Student,
    TemplateRepo,
)

router = APIRouter(prefix="/orgs", tags=["classroom50"])


def _bad_gateway(exc: GhError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"gh teacher falló: {exc}")


@router.get("", response_model=list[Org])
async def list_orgs(gh: GhCliDep) -> list[Org]:
    try:
        return await gh.orgs()
    except GhError as exc:
        raise _bad_gateway(exc) from exc


@router.get("/{org}/classrooms", response_model=list[Classroom])
async def list_classrooms(org: str, gh: GhCliDep) -> list[Classroom]:
    try:
        return await gh.classrooms(org)
    except GhError as exc:
        raise _bad_gateway(exc) from exc


@router.get("/{org}/templates", response_model=list[TemplateRepo])
async def list_templates(org: str, gh: GhCliDep) -> list[TemplateRepo]:
    try:
        return await gh.templates(org)
    except GhError as exc:
        raise _bad_gateway(exc) from exc


@router.get("/{org}/classrooms/{classroom}/assignments", response_model=list[Assignment])
async def list_assignments(org: str, classroom: str, gh: GhCliDep) -> list[Assignment]:
    try:
        return await gh.assignments(org, classroom)
    except GhError as exc:
        raise _bad_gateway(exc) from exc


@router.get("/{org}/classrooms/{classroom}/roster", response_model=list[Student])
async def list_roster(org: str, classroom: str, gh: GhCliDep) -> list[Student]:
    try:
        return await gh.roster(org, classroom)
    except GhError as exc:
        raise _bad_gateway(exc) from exc


@router.get("/{org}/classrooms/{classroom}/staff", response_model=list[Student])
async def list_staff(org: str, classroom: str, gh: GhCliDep) -> list[Student]:
    try:
        return await gh.staff(org, classroom)
    except GhError as exc:
        raise _bad_gateway(exc) from exc
