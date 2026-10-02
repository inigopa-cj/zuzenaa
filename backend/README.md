# ZuzenAA · Backend

Backend FastAPI de ZuzenAA. Orquesta el CLI de Classroom 50 (`gh teacher`/`gh student`) y la capa agéntica.

## Requisitos

- [`uv`](https://docs.astral.sh/uv/) (gestiona Python y dependencias).
- `gh` con las extensiones `gh-teacher`/`gh-student` para las operaciones reales.

## Uso

```sh
uv sync                 # crea .venv e instala deps (incluye el grupo dev)
uv run fastapi dev src/zuzenaa/main.py   # servidor de desarrollo
uv run pytest           # tests
uv run ruff check .     # lint
uv run ruff format .    # formato
uv run mypy             # tipos
```

No hay `requirements.txt`: la fuente de verdad es `pyproject.toml` + `uv.lock`.

## Estructura

```
backend/
  pyproject.toml
  uv.lock
  .python-version
  src/zuzenaa/
    __init__.py
    main.py        # app FastAPI
    config.py      # settings (pydantic-settings)
  tests/
```
