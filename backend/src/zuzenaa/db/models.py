"""ORM models.

Timestamps are stored as epoch seconds (portable across Postgres and SQLite,
and free of timezone-coercion surprises).
"""

from sqlalchemy import BigInteger, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from zuzenaa.db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    github_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    login: Mapped[str] = mapped_column(String(100), index=True)
    name: Mapped[str | None] = mapped_column(String(255))
    avatar_url: Mapped[str | None] = mapped_column(String(500))
    encrypted_token: Mapped[str] = mapped_column(Text)
    created_at: Mapped[int] = mapped_column(BigInteger)
    updated_at: Mapped[int] = mapped_column(BigInteger)


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    created_at: Mapped[int] = mapped_column(BigInteger)
    expires_at: Mapped[int] = mapped_column(BigInteger, index=True)


class OAuthState(Base):
    __tablename__ = "oauth_states"

    state: Mapped[str] = mapped_column(String(64), primary_key=True)
    created_at: Mapped[int] = mapped_column(BigInteger)


class Repository(Base):
    """A student repository downloaded to the server."""

    __tablename__ = "repositories"

    id: Mapped[int] = mapped_column(primary_key=True)
    org: Mapped[str] = mapped_column(String(100), index=True)
    classroom: Mapped[str] = mapped_column(String(100))
    assignment: Mapped[str] = mapped_column(String(100))
    owner: Mapped[str] = mapped_column(String(100), index=True)
    repo_full_name: Mapped[str] = mapped_column(String(200))
    path: Mapped[str] = mapped_column(String(500))
    default_branch: Mapped[str] = mapped_column(String(100), default="main")
    head_sha: Mapped[str | None] = mapped_column(String(64))
    head_committed_at: Mapped[int | None] = mapped_column(BigInteger)
    last_synced_at: Mapped[int | None] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String(20), default="ok")  # ok|missing|error
    detail: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[int] = mapped_column(BigInteger)
    updated_at: Mapped[int] = mapped_column(BigInteger)


class Analysis(Base):
    """One agent analysis (feedback) over a repository commit."""

    __tablename__ = "analyses"

    id: Mapped[int] = mapped_column(primary_key=True)
    repository_id: Mapped[int] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"), index=True
    )
    commit_sha: Mapped[str] = mapped_column(String(64), index=True)
    commit_committed_at: Mapped[int | None] = mapped_column(BigInteger)
    snapshot_path: Mapped[str] = mapped_column(String(500))
    provider: Mapped[str] = mapped_column(String(50))
    feedback_json: Mapped[str] = mapped_column(Text)
    feedback_md: Mapped[str] = mapped_column(Text)
    evolution: Mapped[str | None] = mapped_column(Text)
    tokens_used: Mapped[int] = mapped_column(default=0)
    forced: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[int] = mapped_column(BigInteger, index=True)


class Pseudonym(Base):
    """Seudónimo estable de un alumno dentro de una clase.

    La web y el agente solo ven ``alias`` (p. ej. ``3.URGAA``). El login hace falta
    para clonar desde Classroom 50 y nunca sale del backend; el nombre real se guarda
    **cifrado** (para «Mostrar identidad» y para borrarlo del código antes del agente).
    """

    __tablename__ = "pseudonyms"
    __table_args__ = (
        UniqueConstraint("org", "classroom", "login", name="uq_pseudonym_login"),
        UniqueConstraint("org", "classroom", "alias", name="uq_pseudonym_alias"),
        UniqueConstraint("org", "classroom", "position", name="uq_pseudonym_position"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    org: Mapped[str] = mapped_column(String(100), index=True)
    classroom: Mapped[str] = mapped_column(String(100))
    login: Mapped[str] = mapped_column(String(100))  # en minúsculas
    position: Mapped[int] = mapped_column()
    alias: Mapped[str] = mapped_column(String(32))
    encrypted_name: Mapped[str | None] = mapped_column(Text)  # "nombre|apellidos" cifrado
    created_at: Mapped[int] = mapped_column(BigInteger)
    updated_at: Mapped[int] = mapped_column(BigInteger)


class IdentityReveal(Base):
    """Registro de cada vez que el staff muestra la identidad real de un seudónimo."""

    __tablename__ = "identity_reveals"

    id: Mapped[int] = mapped_column(primary_key=True)
    org: Mapped[str] = mapped_column(String(100), index=True)
    classroom: Mapped[str] = mapped_column(String(100))
    alias: Mapped[str] = mapped_column(String(32))
    viewer_login: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[int] = mapped_column(BigInteger, index=True)


class TutorDocument(Base):
    """Documento del corpus del tutor (RAG).

    ``source``: ``material`` (lo sube el profesorado para una clase) o ``zuzenaa``
    (documentación de la plataforma, común a todas: ``org``/``classroom`` vacíos).
    El feedback del alumno no se guarda aquí: se recupera en cada pregunta y solo el suyo.
    """

    __tablename__ = "tutor_documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    org: Mapped[str | None] = mapped_column(String(100), index=True)
    classroom: Mapped[str | None] = mapped_column(String(100))
    source: Mapped[str] = mapped_column(String(20))  # material | zuzenaa
    title: Mapped[str] = mapped_column(String(200))
    filename: Mapped[str | None] = mapped_column(String(255))
    content_hash: Mapped[str] = mapped_column(String(64))
    uploaded_by: Mapped[str | None] = mapped_column(String(100))
    chunk_count: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[int] = mapped_column(BigInteger)


class TutorChunk(Base):
    """Fragmento indexado de un documento del tutor, con su embedding (JSON)."""

    __tablename__ = "tutor_chunks"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("tutor_documents.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int] = mapped_column()
    heading: Mapped[str | None] = mapped_column(String(200))
    text: Mapped[str] = mapped_column(Text)
    embedding: Mapped[str] = mapped_column(Text)  # lista de floats en JSON


class TutorShare(Base):
    """Duda que el alumno envía a su profesorado desde el tutor, ligada a una corrección.

    Es lo único del tutor que se guarda, y solo si el alumno lo envía. El texto (nota y
    conversación) se guarda ya limpio de datos personales: con el seudónimo, nunca con
    el login ni el nombre.
    """

    __tablename__ = "tutor_shares"

    id: Mapped[int] = mapped_column(primary_key=True)
    org: Mapped[str] = mapped_column(String(100), index=True)
    classroom: Mapped[str] = mapped_column(String(100))
    assignment: Mapped[str] = mapped_column(String(100))
    owner: Mapped[str] = mapped_column(String(100), index=True)  # login (solo backend)
    analysis_id: Mapped[int] = mapped_column(
        ForeignKey("analyses.id", ondelete="CASCADE"), index=True
    )
    note: Mapped[str | None] = mapped_column(Text)
    transcript: Mapped[str] = mapped_column(Text)  # JSON [{role, text}]
    created_at: Mapped[int] = mapped_column(BigInteger, index=True)
    read_at: Mapped[int | None] = mapped_column(BigInteger)
    read_by: Mapped[str | None] = mapped_column(String(100))


class SyncRun(Base):
    """Progress of a bulk repository download."""

    __tablename__ = "sync_runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    org: Mapped[str] = mapped_column(String(100), index=True)
    classroom: Mapped[str] = mapped_column(String(100))
    assignment: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    total: Mapped[int] = mapped_column(default=0)
    processed: Mapped[int] = mapped_column(default=0)
    cloned: Mapped[int] = mapped_column(default=0)
    updated: Mapped[int] = mapped_column(default=0)
    skipped: Mapped[int] = mapped_column(default=0)
    errors: Mapped[int] = mapped_column(default=0)
    detail: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[int] = mapped_column(BigInteger)
    updated_at: Mapped[int] = mapped_column(BigInteger)
