"""Authentication endpoints (GitHub OAuth App + server-side sessions)."""

from __future__ import annotations

import secrets

import httpx
from fastapi import APIRouter, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy import select

from zuzenaa.api.deps import CurrentUserDep, HttpClientDep, SessionDep
from zuzenaa.auth import oauth
from zuzenaa.auth.oauth import OAuthError
from zuzenaa.auth.security import cipher
from zuzenaa.config import settings
from zuzenaa.db.models import OAuthState, User
from zuzenaa.db.models import Session as SessionModel
from zuzenaa.util import now_epoch

router = APIRouter(prefix="/auth", tags=["auth"])

_STATE_TTL_SECONDS = 600


@router.get("/login")
async def login(session: SessionDep) -> RedirectResponse:
    if not settings.oauth_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "OAuth de GitHub no configurado. Define "
                "ZUZENAA_GITHUB_OAUTH_CLIENT_ID y "
                "ZUZENAA_GITHUB_OAUTH_CLIENT_SECRET (ver docs/04-autenticacion.md)."
            ),
        )
    assert settings.github_oauth_client_id is not None
    state = secrets.token_urlsafe(32)
    session.add(OAuthState(state=state, created_at=now_epoch()))
    await session.commit()
    url = oauth.build_authorize_url(
        client_id=settings.github_oauth_client_id,
        redirect_uri=settings.oauth_redirect_uri,
        scopes=settings.github_oauth_scopes,
        state=state,
    )
    return RedirectResponse(url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)


@router.get("/status")
async def auth_status() -> dict[str, object]:
    """Lets the UI tell 'login con GitHub' from 'OAuth sin configurar'."""
    return {
        "oauth_configured": settings.oauth_configured,
        "env_token_allowed": settings.allow_env_token,
        "scopes": settings.github_oauth_scopes,
        "callback_url": settings.oauth_redirect_uri,
        "classroom50_url": settings.classroom50_url.rstrip("/"),
    }


@router.get("/callback")
async def callback(
    code: str,
    state: str,
    session: SessionDep,
    client: HttpClientDep,
) -> RedirectResponse:
    if not settings.oauth_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OAuth no configurado",
        )
    assert settings.github_oauth_client_id is not None
    assert settings.github_oauth_client_secret is not None

    state_row = await session.get(OAuthState, state)
    if state_row is None or state_row.created_at + _STATE_TTL_SECONDS < now_epoch():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="state inválido o caducado",
        )
    await session.delete(state_row)

    try:
        token = await oauth.exchange_code(
            client,
            client_id=settings.github_oauth_client_id,
            client_secret=settings.github_oauth_client_secret.get_secret_value(),
            code=code,
            redirect_uri=settings.oauth_redirect_uri,
        )
        gh_user = await oauth.fetch_user(client, token)
    except (OAuthError, httpx.HTTPError) as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Fallo al autenticar con GitHub: {exc}",
        ) from exc

    now = now_epoch()
    user = (
        await session.execute(select(User).where(User.github_id == gh_user.id))
    ).scalar_one_or_none()
    if user is None:
        user = User(
            github_id=gh_user.id,
            login=gh_user.login,
            name=gh_user.name,
            avatar_url=gh_user.avatar_url,
            encrypted_token=cipher.encrypt(token),
            created_at=now,
            updated_at=now,
        )
        session.add(user)
        await session.flush()
    else:
        user.login = gh_user.login
        user.name = gh_user.name
        user.avatar_url = gh_user.avatar_url
        user.encrypted_token = cipher.encrypt(token)
        user.updated_at = now

    session_id = secrets.token_urlsafe(32)
    session.add(
        SessionModel(
            id=session_id,
            user_id=user.id,
            created_at=now,
            expires_at=now + settings.session_ttl_seconds,
        )
    )
    await session.commit()

    response = RedirectResponse(settings.frontend_url, status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(
        settings.session_cookie_name,
        session_id,
        max_age=settings.session_ttl_seconds,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )
    return response


@router.post("/logout")
async def logout(request: Request, session: SessionDep) -> Response:
    session_id = request.cookies.get(settings.session_cookie_name)
    if session_id:
        row = await session.get(SessionModel, session_id)
        if row is not None:
            await session.delete(row)
            await session.commit()
    response = JSONResponse({"status": "ok"})
    response.delete_cookie(settings.session_cookie_name, path="/")
    return response


@router.get("/me")
async def me(user: CurrentUserDep) -> dict[str, str | None]:
    return {"login": user.login, "name": user.name, "avatar_url": user.avatar_url}
