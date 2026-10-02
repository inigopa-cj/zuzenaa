"""GitHub OAuth App flow (authorize / token exchange / user fetch)."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlencode

import httpx

AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
TOKEN_URL = "https://github.com/login/oauth/access_token"
USER_URL = "https://api.github.com/user"


class OAuthError(RuntimeError):
    """Raised when an OAuth step fails or GitHub returns an unexpected payload."""


@dataclass(frozen=True)
class GithubUser:
    id: int
    login: str
    name: str | None
    avatar_url: str | None


def build_authorize_url(
    *, client_id: str, redirect_uri: str, scopes: str, state: str
) -> str:
    query = urlencode(
        {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": scopes,
            "state": state,
        }
    )
    return f"{AUTHORIZE_URL}?{query}"


async def exchange_code(
    client: httpx.AsyncClient,
    *,
    client_id: str,
    client_secret: str,
    code: str,
    redirect_uri: str,
) -> str:
    response = await client.post(
        TOKEN_URL,
        headers={"Accept": "application/json"},
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "redirect_uri": redirect_uri,
        },
    )
    response.raise_for_status()
    payload = response.json()
    token = payload.get("access_token") if isinstance(payload, dict) else None
    if not isinstance(token, str) or not token:
        raise OAuthError(f"GitHub no devolvió access_token: {payload!r}")
    return token


async def fetch_user(client: httpx.AsyncClient, token: str) -> GithubUser:
    response = await client.get(
        USER_URL,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
        },
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict) or "id" not in payload or "login" not in payload:
        raise OAuthError(f"respuesta de usuario inesperada: {payload!r}")
    name = payload.get("name")
    avatar = payload.get("avatar_url")
    return GithubUser(
        id=int(payload["id"]),
        login=str(payload["login"]),
        name=str(name) if name is not None else None,
        avatar_url=str(avatar) if avatar is not None else None,
    )
