# AGENTS.md

## Estado del repo

**Plataforma de evaluación con repositorios locales + histórico de feedback** sobre Classroom 50.
Empieza por `docs/00`–`docs/05` y `docs/diagramas/`. Se reutiliza: auth, adaptador `gh` (solo
lectura), agente/guardarraíles y el stack dockerizado. **No** hay que gestionar clases/roster/
assignments/tests (eso es Classroom 50) ni publicar el feedback en la PR. **No** hay n8n.

## Qué es el proyecto

- Classroom 50 sigue siendo la autoridad de **clases, assignments y tests**; ZuzenAA solo **lee**.
- ZuzenAA **descarga** los repos de los alumnos al servidor (clon + snapshots), **evalúa** el
  código local con un **agente**, y guarda **histórico** (fecha + commit) y **progreso**.
- Web: superficie **profesor** (elegir assignment → descargar → analizar → histórico) y **alumno**
  (sus clases/assignments y todo su histórico). El feedback vive **solo** en la plataforma.
- Almacenamiento en **disco del servidor**: `<org>/<classroom>/<assignment>/{repos,snapshots}/<owner>`.

## Stack y arranque

Backend FastAPI (`backend/`, uv), web React/TS + Vite (`web/`), Postgres, SQLAlchemy async,
Docker Compose. Comandos abajo.

## Auth (implementado, se mantiene)

- Flujo OAuth App: `GET /auth/login` → GitHub → `GET /auth/callback`; `GET /auth/me`,
  `POST /auth/logout`. Sesión en cookie `zuzenaa_session`.
- El token se **cifra en reposo** (Fernet derivado de `ZUZENAA_SECRET_KEY`) y se resuelve **por
  petición** (`api/deps.py: get_github_token`): sesión si existe; si no, `ZUZENAA_GITHUB_TOKEN`
  **solo si** `ZUZENAA_ALLOW_ENV_TOKEN=true` (atajo local).
- Guía de OAuth: `docs/04-autenticacion.md`.

## API (implementado)

- **Lectura de Classroom 50** (`api/orgs.py`): `GET /orgs`, `GET /orgs/{org}/classrooms`,
  `.../{c}/assignments`, `.../{c}/roster`, `.../{c}/staff`, `GET /orgs/{org}/templates`.
- **Repos** (`api/repos.py`): `GET .../assignments/{a}/repos` (estado por alumno),
  `POST .../assignments/{a}/repos/sync` (descarga/actualiza clones a disco).
- **Análisis** (`api/analyses.py`): `POST .../assignments/{a}/analysis` (`{owner?, force?}`),
  `GET .../assignments/{a}/repos/{owner}/analyses` (histórico, con `feedback` estructurado).
  La lectura del histórico está **autorizada**: el alumno (sesión) solo ve lo suyo; el **staff**
  de la clase (`gh teacher staff`) ve a cualquiera; sin sesión solo pasa el atajo `allow_env_token`.
- **Superficie alumno** (`api/me.py`): `GET /me/assignments` (descubrimiento desde la BD: lo que el
  profesor ya descargó/analizó para el login).
- **Agente** (`agent/`): worker con proveedor `mock` por defecto (`ZUZENAA_LLM_PROVIDER`);
  guardarraíles; escribe snapshot + `feedback.md` + `analyses.json` y la fila `analyses`.
  El contexto es **real**: `agent/context.py` resume el clon local (árbol, lenguajes, señales)
  y calcula el **diff acotado** (`ZUZENAA_AGENT_MAX_DIFF_CHARS`) contra el commit del
  análisis anterior; el proveedor recibe ese contexto, no una plantilla genérica.
- El adaptador `gh` (`github/cli.py`) es **solo lectura**.

## Estructura en disco y BD

- `DATA_ROOT` (volumen `data`, montado en `/data`):
  `<org>/<classroom>/<assignment>/{repos/<owner>, snapshots/<owner>/<fecha>-<sha>, analyses.json}`.
- BD: `users`, `sessions`, `oauth_states`, `repositories`, `analyses`, `sync_runs`.
- El esquema se crea con `create_all` al arrancar (temporal; migrar a Alembic al estabilizar).

## Comandos

Todo el proyecto está dockerizado. Desde la raíz:

- `make up` / `make down` — arranca/para db + backend + web (web en `:8080`, API en `:8000`).
- `make dev` / `make dev-down` — modo desarrollo con recarga (web en `:5173`).
- `make logs`, `make ps`, `make clean` (borra volúmenes), `make help`.

Backend (desde `backend/`, uv): `uv sync`, `uv run pytest`, `uv run ruff check .`, `uv run mypy`.
Web (desde `web/`): `npm run dev`, `npm run build`, `npm run lint`.

## Hechos verificados de Classroom 50 (v1.56.1)

- Es **100% client-side**: el estado vive en GitHub (`classroom50` repo, Teams, Releases, `scores.json`).
- CLI `gh teacher` (extensión `gh`): `--json` en **stdout**, resumen en **stderr** (leer solo stdout).
- **Roster**: la autoridad es el **equipo** `classroom50-<clase>`; el CSV (`roster.csv`/`students.csv`)
  solo enriquece. Staff: tolerar `instructor`/`hta` y `teacher`/`hta`.
- Los **tests** corren en GitHub Actions; ZuzenAA **no** los re-ejecuta.
- Nombrado del repo de alumno: `<classroom>-<assignment>-<owner>` (minúsculas).
- Licencia **GPL-3.0**: consumir el CLI como binario separado; no copiar código upstream.
