# syntax=docker/dockerfile:1

# ---------------------------------------------------------------------------
# base: sistema + gh (GitHub CLI) + extensiones gh-teacher/gh-student + uv
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never

# uv (gestor de Python/dependencias)
COPY --from=ghcr.io/astral-sh/uv:0.12.13 /uv /uvx /bin/

# git + gh CLI + extensiones de Classroom 50 (versión fija)
ARG GH_EXT_VERSION=v1.56.1
RUN apt-get update \
    && apt-get install -y --no-install-recommends git curl ca-certificates gnupg \
    && curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
         -o /usr/share/keyrings/githubcli-archive-keyring.gpg \
    && chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
         > /etc/apt/sources.list.d/github-cli.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends gh \
    && rm -rf /var/lib/apt/lists/* \
    && gh extension install foundation50/gh-teacher --pin "${GH_EXT_VERSION}" \
    && gh extension install foundation50/gh-student --pin "${GH_EXT_VERSION}"

WORKDIR /app

# ---------------------------------------------------------------------------
# dependencies: resuelve el lock (sin el proyecto) para cachear capas
# ---------------------------------------------------------------------------
FROM base AS dependencies
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

# ---------------------------------------------------------------------------
# runtime: imagen de producción
# ---------------------------------------------------------------------------
FROM dependencies AS runtime
COPY README.md ./
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev
ENV PATH="/app/.venv/bin:${PATH}" \
    ZUZENAA_DEBUG=false
EXPOSE 8000
CMD ["uvicorn", "zuzenaa.main:app", "--host", "0.0.0.0", "--port", "8000"]

# ---------------------------------------------------------------------------
# dev: con dependencias de desarrollo y recarga en caliente
# ---------------------------------------------------------------------------
FROM dependencies AS dev
COPY README.md ./
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen
ENV PATH="/app/.venv/bin:${PATH}"
EXPOSE 8000
CMD ["fastapi", "dev", "src/zuzenaa/main.py", "--host", "0.0.0.0", "--port", "8000"]
