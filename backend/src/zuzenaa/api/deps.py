"""FastAPI dependencies.

The GitHub token is resolved per request: from the authenticated session when
present, otherwise from ``ZUZENAA_GITHUB_TOKEN`` only if
``allow_env_token`` is on (a local/dev convenience).
"""

from typing import Annotated, cast

import httpx
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from zuzenaa.auth.security import cipher
from zuzenaa.config import settings
from zuzenaa.db.models import Session as SessionModel
from zuzenaa.db.models import User
from zuzenaa.db.session import get_session
from zuzenaa.github.cli import GhCli
from zuzenaa.util import now_epoch

SessionDep = Annotated[AsyncSession, Depends(get_session)]


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No autenticado.",
    )


def get_http_client(request: Request) -> httpx.AsyncClient:
    return cast(httpx.AsyncClient, request.app.state.http)


HttpClientDep = Annotated[httpx.AsyncClient, Depends(get_http_client)]


async def _session_user(request: Request, session: AsyncSession) -> User | None:
    session_id = request.cookies.get(settings.session_cookie_name)
    if not session_id:
        return None
    row = await session.get(SessionModel, session_id)
    if row is None or row.expires_at < now_epoch():
        return None
    return await session.get(User, row.user_id)


async def get_current_user(request: Request, session: SessionDep) -> User:
    user = await _session_user(request, session)
    if user is None:
        raise _unauthorized()
    return user


CurrentUserDep = Annotated[User, Depends(get_current_user)]


async def get_optional_user(request: Request, session: SessionDep) -> User | None:
    """Session user if present, else ``None`` (no 401)."""
    return await _session_user(request, session)


OptionalUserDep = Annotated[User | None, Depends(get_optional_user)]


async def get_github_token(request: Request, session: SessionDep) -> str:
    user = await _session_user(request, session)
    if user is not None:
        return cipher.decrypt(user.encrypted_token)
    if settings.allow_env_token and settings.github_token is not None:
        return settings.github_token.get_secret_value()
    raise _unauthorized()


def get_gh_cli(token: Annotated[str, Depends(get_github_token)]) -> GhCli:
    return GhCli(token=token, gh_binary=settings.gh_binary, timeout=settings.gh_timeout)


GhCliDep = Annotated[GhCli, Depends(get_gh_cli)]
