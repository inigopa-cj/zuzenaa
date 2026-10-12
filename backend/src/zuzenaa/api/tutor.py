"""Tutor RAG: chat del alumnado y material del tutor (gestionado por el profesorado).

- ``POST /tutor/orgs/{org}/classrooms/{c}/chat``: alumnado de la clase (sus dudas, con
  su propio feedback) o staff (sin alumno, o con ``as=<seudónimo>`` para ver qué le
  respondería a ese alumno). Nunca se usa el feedback de otro alumno.
- ``GET|POST|DELETE /tutor/orgs/{org}/classrooms/{c}/documents``: material de la clase,
  solo staff. Se admiten ``.md`` y ``.txt``.
- ``.../assignments/{a}/repos/{owner}/shares``: dudas que el alumno **envía a su
  profesorado** desde una corrección (``POST`` solo el propio alumno; ``GET`` el alumno
  o el staff) y ``POST .../shares/{id}/read`` (staff) para marcarlas como leídas.

Las conversaciones no se guardan, salvo lo que el alumno decide enviar al profesorado,
que se guarda ya limpio de datos personales (con su seudónimo).
"""

import json
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from zuzenaa.api.analyses import _authorize_owner, authorize_staff, owner_login
from zuzenaa.api.deps import GhCliDep, OptionalUserDep
from zuzenaa.auth.roles import resolve_role
from zuzenaa.config import settings
from zuzenaa.db.models import Analysis, Repository, TutorShare, User
from zuzenaa.db.session import SessionLocal
from zuzenaa.github.cli import GhCli
from zuzenaa.privacy import pseudonyms
from zuzenaa.privacy.scrub import scrub
from zuzenaa.tutor import service, store
from zuzenaa.util import now_epoch

router = APIRouter(prefix="/tutor/orgs/{org}/classrooms/{classroom}", tags=["tutor"])

MAX_UPLOAD_BYTES = 2_000_000


def _no_correction() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="corrección no encontrada")
ALLOWED_SUFFIXES = (".md", ".markdown", ".txt")


class ChatIn(BaseModel):
    question: str = Field(min_length=1, max_length=service.MAX_QUESTION_CHARS)
    assignment: str | None = None
    as_alias: str | None = Field(default=None, alias="as")  # vista previa del staff
    analysis_id: int | None = None  # corrección desde la que se abre el tutor


class CitationOut(BaseModel):
    number: int
    source: str
    title: str
    heading: str | None
    snippet: str
    ref: str


class ChatOut(BaseModel):
    answer: str
    citations: list[CitationOut]
    blocked: bool
    provider: str


class DocumentOut(BaseModel):
    id: int
    title: str
    filename: str | None
    chunk_count: int
    created_at: int


async def _owns_repo_in(org: str, classroom: str, login: str) -> bool:
    async with SessionLocal() as session:
        count = (
            await session.execute(
                select(func.count(Repository.id)).where(
                    Repository.org == org,
                    Repository.classroom == classroom,
                    func.lower(Repository.owner) == login.lower(),
                )
            )
        ).scalar_one()
    return bool(count)


async def _asker(
    org: str, classroom: str, payload: ChatIn, user: User | None, gh: GhCli
) -> str | None:
    """Login del alumno cuya duda se responde (``None``: staff sin alumno)."""
    if user is None:
        if settings.allow_env_token:
            return None
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No autenticado.")
    info = await resolve_role(user.login, gh)
    if info.is_staff_of(org, classroom):
        if payload.as_alias is None:
            return None
        login = await pseudonyms.resolve(org, classroom, payload.as_alias)
        if login is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="alumno no encontrado"
            )
        return login
    if payload.as_alias is None and await _owns_repo_in(org, classroom, user.login):
        return user.login
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="El tutor de esta clase es solo para su alumnado y profesorado.",
    )


@router.post("/chat", response_model=ChatOut)
async def chat(
    org: str, classroom: str, payload: ChatIn, user: OptionalUserDep, gh: GhCliDep
) -> ChatOut:
    login = await _asker(org, classroom, payload, user, gh)
    correction = None
    if payload.analysis_id is not None:
        correction = await service.load_correction(org, classroom, payload.analysis_id)
        # Solo correcciones del propio alumno (o del alumno previsualizado por el staff).
        foreign = login is not None and correction is not None and (
            correction.owner.lower() != login.lower()
        )
        if correction is None or foreign:
            raise _no_correction()
        if login is None:  # staff sin vista previa: la duda es sobre ese alumno
            login = correction.owner
    reply = await service.ask(
        org=org,
        classroom=classroom,
        question=payload.question,
        login=login,
        assignment=correction.assignment if correction else payload.assignment,
        correction=correction,
    )
    return ChatOut(
        answer=reply.answer,
        citations=[CitationOut(**vars(c)) for c in reply.citations],
        blocked=reply.blocked,
        provider=reply.provider,
    )


async def _staff_only(org: str, classroom: str, user: User | None, gh: GhCli) -> None:
    await authorize_staff(
        org=org,
        classroom=classroom,
        user=user,
        gh=gh,
        denied="Solo el profesorado de la clase gestiona el material del tutor.",
    )


def _out(document: object) -> DocumentOut:
    return DocumentOut.model_validate(document, from_attributes=True)


@router.get("/documents", response_model=list[DocumentOut])
async def list_documents(
    org: str, classroom: str, user: OptionalUserDep, gh: GhCliDep
) -> list[DocumentOut]:
    await _staff_only(org, classroom, user, gh)
    return [_out(doc) for doc in await store.documents(org, classroom)]


@router.post("/documents", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
async def upload_document(
    org: str,
    classroom: str,
    user: OptionalUserDep,
    gh: GhCliDep,
    file: Annotated[UploadFile, File()],
    title: Annotated[str | None, Form()] = None,
) -> DocumentOut:
    await _staff_only(org, classroom, user, gh)
    name = file.filename or "documento.md"
    if not name.lower().endswith(ALLOWED_SUFFIXES):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Por ahora solo se admiten ficheros .md y .txt.",
        )
    raw = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="El fichero supera los 2 MB.",
        )
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="El fichero debe estar en UTF-8."
        ) from exc
    if not text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="El fichero está vacío."
        )
    document = await store.ingest(
        title=(title or name.rsplit(".", 1)[0]).strip(),
        text=text,
        source="material",
        org=org,
        classroom=classroom,
        filename=name,
        uploaded_by=user.login if user is not None else None,
    )
    return _out(document)


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    org: str, classroom: str, document_id: int, user: OptionalUserDep, gh: GhCliDep
) -> None:
    await _staff_only(org, classroom, user, gh)
    if not await store.remove(org, classroom, document_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="documento no encontrado")


# --- Envíos al profesorado ----------------------------------------------------------

MAX_TRANSCRIPT_MESSAGES = 40
MAX_MESSAGE_CHARS = 4000


class TranscriptMessage(BaseModel):
    role: str = Field(pattern="^(user|tutor)$")
    text: str = Field(max_length=MAX_MESSAGE_CHARS)


class ShareIn(BaseModel):
    analysis_id: int
    note: str | None = Field(default=None, max_length=2000)
    transcript: list[TranscriptMessage] = Field(default=[], max_length=MAX_TRANSCRIPT_MESSAGES)


class ShareOut(BaseModel):
    id: int
    analysis_id: int
    commit_sha: str
    note: str | None
    transcript: list[TranscriptMessage]
    created_at: int
    read_at: int | None


async def _share_out(share: TutorShare) -> ShareOut:
    async with SessionLocal() as session:
        analysis = await session.get(Analysis, share.analysis_id)
    return ShareOut(
        id=share.id,
        analysis_id=share.analysis_id,
        commit_sha=analysis.commit_sha if analysis else "",
        note=share.note,
        transcript=[TranscriptMessage(**m) for m in json.loads(share.transcript)],
        created_at=share.created_at,
        read_at=share.read_at,
    )


SHARES = "/assignments/{assignment}/repos/{owner}/shares"


@router.post(SHARES, response_model=ShareOut, status_code=status.HTTP_201_CREATED)
async def send_to_teacher(
    org: str,
    classroom: str,
    assignment: str,
    owner: str,
    payload: ShareIn,
    user: OptionalUserDep,
) -> ShareOut:
    """El alumno envía su duda (nota + conversación) a su profesorado, ligada a una corrección."""
    login = await owner_login(org, classroom, owner)
    if user is None or user.login.lower() != login:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo el propio alumno puede enviar sus dudas al profesorado.",
        )
    correction = await service.load_correction(org, classroom, payload.analysis_id)
    if (
        correction is None
        or correction.owner.lower() != login
        or correction.assignment != assignment
    ):
        raise _no_correction()
    if not (payload.note or "").strip() and not payload.transcript:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Escribe una nota o incluye la conversación.",
        )

    # Privacidad: lo que se guarda va con el seudónimo, nunca con el login ni el nombre.
    terms = await pseudonyms.personal_terms(org, classroom, login)
    note = str(scrub(payload.note.strip(), terms, owner)) if payload.note else None
    transcript = [
        {"role": m.role, "text": str(scrub(m.text, terms, owner))} for m in payload.transcript
    ]
    share = TutorShare(
        org=org,
        classroom=classroom,
        assignment=assignment,
        owner=login,
        analysis_id=payload.analysis_id,
        note=note or None,
        transcript=json.dumps(transcript, ensure_ascii=False),
        created_at=now_epoch(),
    )
    async with SessionLocal() as session:
        session.add(share)
        await session.commit()
        await session.refresh(share)
    return await _share_out(share)


@router.get(SHARES, response_model=list[ShareOut])
async def list_shares(
    org: str, classroom: str, assignment: str, owner: str, user: OptionalUserDep, gh: GhCliDep
) -> list[ShareOut]:
    """Dudas enviadas por un alumno en una entrega: el propio alumno o el staff."""
    login = await owner_login(org, classroom, owner)
    await _authorize_owner(org=org, classroom=classroom, owner=login, user=user, gh=gh)
    async with SessionLocal() as session:
        rows = (
            await session.execute(
                select(TutorShare)
                .where(
                    TutorShare.org == org,
                    TutorShare.classroom == classroom,
                    TutorShare.assignment == assignment,
                    TutorShare.owner == login,
                )
                .order_by(TutorShare.created_at.desc())
            )
        ).scalars().all()
    return [await _share_out(row) for row in rows]


@router.post("/shares/{share_id}/read", response_model=ShareOut)
async def mark_read(
    org: str, classroom: str, share_id: int, user: OptionalUserDep, gh: GhCliDep
) -> ShareOut:
    await _staff_only(org, classroom, user, gh)
    async with SessionLocal() as session:
        share = await session.get(TutorShare, share_id)
        if share is None or (share.org, share.classroom) != (org, classroom):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="duda no encontrada")
        if share.read_at is None:
            share.read_at = now_epoch()
            share.read_by = user.login if user is not None else None
            await session.commit()
            await session.refresh(share)
    return await _share_out(share)
