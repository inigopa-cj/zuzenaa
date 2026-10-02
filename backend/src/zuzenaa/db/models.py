"""ORM models.

Timestamps are stored as epoch seconds (portable across Postgres and SQLite,
and free of timezone-coercion surprises).
"""

from sqlalchemy import BigInteger, ForeignKey, String, Text
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
