"""FastAPI application entrypoint."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from zuzenaa import __version__
from zuzenaa.api.analyses import router as analyses_router
from zuzenaa.api.auth import router as auth_router
from zuzenaa.api.me import router as me_router
from zuzenaa.api.orgs import router as orgs_router
from zuzenaa.api.repos import router as repos_router
from zuzenaa.config import settings
from zuzenaa.db.session import init_models


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    await init_models()
    app.state.http = httpx.AsyncClient()
    try:
        yield
    finally:
        await app.state.http.aclose()


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name, version=__version__, lifespan=lifespan)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(auth_router)
    app.include_router(me_router)
    app.include_router(orgs_router)
    app.include_router(repos_router)
    app.include_router(analyses_router)

    return app


app = create_app()
