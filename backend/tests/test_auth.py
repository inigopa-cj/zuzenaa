from collections.abc import Iterator
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from fastapi.testclient import TestClient

from zuzenaa.api.deps import get_http_client
from zuzenaa.main import app


def _transport() -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/login/oauth/access_token":
            return httpx.Response(200, json={"access_token": "gho_test"})
        if request.url.path == "/user":
            return httpx.Response(
                200,
                json={
                    "id": 7,
                    "login": "octocat",
                    "name": "Mona",
                    "avatar_url": "https://example.test/a.png",
                },
            )
        return httpx.Response(404)

    return httpx.MockTransport(handler)


@pytest.fixture
def client() -> Iterator[TestClient]:
    app.dependency_overrides[get_http_client] = lambda: httpx.AsyncClient(transport=_transport())
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _authenticate(client: TestClient) -> None:
    response = client.get("/auth/login", follow_redirects=False)
    assert response.status_code == 307
    state = parse_qs(urlparse(response.headers["location"]).query)["state"][0]
    callback = client.get(f"/auth/callback?code=abc&state={state}", follow_redirects=False)
    assert callback.status_code == 303


def test_oauth_login_flow(client: TestClient) -> None:
    _authenticate(client)
    me = client.get("/auth/me")
    assert me.status_code == 200
    assert me.json()["login"] == "octocat"


def test_callback_rejects_unknown_state(client: TestClient) -> None:
    response = client.get("/auth/callback?code=abc&state=nope", follow_redirects=False)
    assert response.status_code == 400


def test_logout_clears_session(client: TestClient) -> None:
    _authenticate(client)
    assert client.post("/auth/logout").status_code == 200
    assert client.get("/auth/me").status_code == 401


def test_auth_status_reports_oauth_configured(client: TestClient) -> None:
    response = client.get("/auth/status")
    assert response.status_code == 200
    assert response.json()["oauth_configured"] is True


def test_login_returns_503_when_unconfigured(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from zuzenaa.config import settings

    monkeypatch.setattr(settings, "github_oauth_client_secret", None)
    response = client.get("/auth/login", follow_redirects=False)
    assert response.status_code == 503
