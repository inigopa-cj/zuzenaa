# AGENTS.md

## Estado del repo

**Plataforma de evaluación con repositorios locales + histórico de feedback** sobre Classroom 50.
Empieza por `docs/00`–`docs/05` y `docs/diagramas/`. Se reutiliza: auth, adaptador `gh` (solo
lectura), agente/guardarraíles y el stack dockerizado. **No** hay que gestionar clases/roster/
assignments/tests (eso es Classroom 50) ni publicar el feedback en la PR. **No** hay n8n.

## Privacidad del alumnado (regla dura)

- En la web el alumnado aparece **solo con su seudónimo de clase**: `<posición>.<AP1><AP2><N>`
  (p. ej. `3.URGAA` = n.º 3, **UR**rutia **GA**rmendia, **A**ne). Posición fijada la primera vez
  (orden de lista por apellidos; los nuevos al final), así que el código no cambia nunca.
  Es por clase y el mismo en todos los procesos (tablas, fichas, URLs, análisis, progreso).
- La API habla en seudónimos: `{owner}` en rutas y `owner` en respuestas son el código; el login
  solo existe dentro del backend (clonar). Tabla `pseudonyms` (`privacy/pseudonyms.py`; nombre
  real **cifrado**).
- **La identidad nunca llega al agente/LLM** (nada puede salir a internet): el contexto lleva el
  seudónimo y `privacy/scrub.py` sustituye login, nombre y apellidos en código, diff, rutas y
  feedback previo; si aun así queda alguno, el análisis se **bloquea**.
- «Mostrar identidad» (`GET .../repos/{owner}/identity`): solo staff de la clase, cada consulta
  queda en `identity_reveals`. Es el único punto que devuelve la identidad real.

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
- **Análisis** (`api/analyses.py`): `POST .../assignments/{a}/analysis` (`{owner?, force?}`)
  **descarga el último push y lo analiza** (`agent/service.py: sync_and_analyze`; mismo camino que
  el push simulado de la demo),
  `GET .../assignments/{a}/repos/{owner}/analyses` (histórico, con `feedback` estructurado).
  La lectura del histórico está **autorizada**: el alumno (sesión) solo ve lo suyo; el **staff**
  de la clase (`gh teacher staff`) ve a cualquiera; sin sesión solo pasa el atajo `allow_env_token`.
- **Progreso** (`api/progress.py`, `progress/`): `GET .../assignments/{a}/repos/{owner}/progress`
  (progreso del alumno; misma autorización que el histórico) y `GET .../assignments/{a}/progress`
  (evolución de la clase; **solo staff**). Se calcula al leer sobre `analyses` + `git log`; la
  vista de clase **agrega** el progreso de cada alumno (una sola fuente de verdad).
- **Superficie alumno** (`api/me.py`): `GET /me/role` (rol detectado: `staff` si está en el staff
  de alguna clase conocida, `student` si solo tiene entregas, `unknown` si nada; `auth/roles.py`,
  caché 5 min) y `GET /me/assignments` (descubrimiento desde la BD + resumen de progreso por
  entrega; `?as=<login>` = vista previa del profesorado, solo sus clases).
- **Gestión solo para staff**: `GET .../repos`, `POST .../repos/sync`, `POST .../analysis` y el
  push de la demo exigen ser staff de la clase (`api/analyses.py: require_staff`).
- **Agente** (`agent/`): worker con proveedor `mock` por defecto (`ZUZENAA_LLM_PROVIDER`);
  guardarraíles; escribe snapshot + `feedback.md` + `analyses.json` y la fila `analyses`.
  El contexto es **real**: `agent/context.py` resume el clon local (árbol, lenguajes, señales)
  y calcula el **diff acotado** (`ZUZENAA_AGENT_MAX_DIFF_CHARS`) contra el commit del
  análisis anterior; el proveedor recibe ese contexto, no una plantilla genérica. También
  recibe el **resultado de los tests** del commit (`github/results.py`, solo lectura; hoy solo
  en modo demo), que se guarda en `feedback_json.tests`.
- **Modo demo** (`ZUZENAA_DEMO_MODE=true`, `docs/06-datos-de-prueba.md`): emula Classroom 50 en
  local; `POST /demo/.../repos/{owner}/push` simula un push (tests + descarga + análisis).
- El adaptador `gh` (`github/cli.py`) es **solo lectura**.

## Estructura en disco y BD

- `DATA_ROOT` (volumen `data`, montado en `/data`):
  `<org>/<classroom>/<assignment>/{repos/<owner>, snapshots/<owner>/<fecha>-<sha>, analyses.json}`.
- BD: `users`, `sessions`, `oauth_states`, `repositories`, `analyses`, `sync_runs`,
  `pseudonyms`, `identity_reveals`.
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
