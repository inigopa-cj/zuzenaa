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
- **La identidad nunca llega al agente/LLM** (aunque el tutor use una API remota): el contexto lleva el
  seudónimo y `privacy/scrub.py` sustituye login, nombre y apellidos en código, diff, rutas y
  feedback previo; si aun así queda alguno, el análisis se **bloquea**.
- «Mostrar identidad» (`GET .../repos/{owner}/identity`): solo staff de la clase, cada consulta
  queda en `identity_reveals`. Es el único punto que devuelve la identidad real.

## Agentes del sistema (reglas para tocarlos o crear nuevos)

### Inventario y contrato

| Agente | Dónde | Entrada | Herramientas | Salida | Proveedor |
| --- | --- | --- | --- | --- | --- |
| **Feedback** (corrige cada commit) | `agent/` (`worker.py: _PROMPT`, `llm.py`, `schema.py`) | contexto del repo limpio (árbol, señales, diff acotado, tests, feedback previo) | ninguna | `AgentFeedback` (funcionalidad, calidad, diseño, pista, teoría) | `ZUZENAA_LLM_PROVIDER` (hoy solo `mock`) |
| **Tutor** (dudas del alumno) | `tutor/agent.py` (`SYSTEM_PROMPT`), `tutor/models.py`, `tutor/service.py` | duda limpia + corrección + fragmentos numerados (apuntes, guía, feedback propio) | `buscar_apuntes` (máx. 2), `responder` | `TutorAnswer` (respuesta, preguntas guía, pasos, apuntes con motivo) | `ZUZENAA_TUTOR_PROVIDER`: `anthropic`, `openai_compatible` o `mock` |

### Invariantes (ningún cambio puede romperlas)

1. **Privacidad**: todo texto hacia un modelo pasa por `privacy/scrub.py: scrub` y se comprueba
   con `leaks` **antes de cada llamada** (no solo la primera). Si queda un dato personal, no se
   envía: se bloquea.
2. **Nunca código hacia el alumno**: toda salida visible pasa `agent/guardrails.py:
   text_violation`. El tutor tiene una reescritura (`MAX_REWRITES`) y luego bloquea.
3. **Solo salidas estructuradas y validadas** (Pydantic). Nunca se muestra texto libre del modelo.
4. **Citas solo de fragmentos recuperados**: las referencias `[n]` fuera del registro se descartan.
5. **Respaldo sin modelo**: sin clave o ante `ProviderError`, responde el `mock` con la misma
   estructura y un aviso; la plataforma nunca se queda sin respuesta.
6. **Gasto acotado**: límite por usuario y hora en el tutor; pasos y búsquedas acotados en el
   bucle (`MAX_STEPS`, `MAX_SEARCHES`).
7. **Tests sin red**: los agentes se prueban con un modelo simulado guionizado
   (`tests/test_tutor_agent.py: Scripted`); ningún test llama a una API real.

### Checklist para añadir un agente nuevo

- [ ] Va detrás de una interfaz de proveedor (como `ChatModel` en `tutor/models.py`), elegible
      por `.env`, con `mock` por defecto.
- [ ] Esquema de salida Pydantic (y herramientas con `additionalProperties: false`).
- [ ] Privacidad: seudónimo + `scrub` + `leaks` antes de cada llamada.
- [ ] Guardarraíles sobre todo texto visible (`text_violation`) y política de reintento/bloqueo.
- [ ] Respaldo sin modelo y manejo de rechazos (`stop == "refusal"`) y errores del proveedor.
- [ ] Límites de pasos, de herramientas y de gasto.
- [ ] Tests con modelo simulado: camino feliz, reescritura, bloqueo, fuga de datos, respaldo.
- [ ] Documentado aquí (tabla de arriba) y en `docs/01-arquitectura.md`.

### Política de modelos y prompts

- El modelo se cambia por `.env` (`ZUZENAA_TUTOR_MODEL`), nunca en el código. Por defecto
  `claude-opus-5-5`; `claude-haiku-5-5` es ~40 veces más barato (coste orientativo por
  respuesta del tutor en `docs/05-guia-configuracion.md`).
- Con `anthropic` se usa el **SDK oficial** (no un endpoint compatible con OpenAI). Los modelos
  que lo admiten llevan *fallbacks* del servidor ante rechazos.
- **Cambiar un prompt (`SYSTEM_PROMPT`, `_PROMPT`) o el modelo exige pasar la evaluación del
  tutor** (`backend/evals/tutor/`, ver su README) y comparar con la línea base. No se aceptan
  cambios de prompt «a ojo».

### Huecos conocidos

- No se registra el gasto: `analyses.tokens_used` vale siempre 0 y el tutor no guarda tokens ni
  modelo por respuesta.
- El tutor no se ha probado aún contra una API real (falta clave del proveedor).
- El agente de feedback solo tiene proveedor `mock`.

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
- **Tutor RAG** (`api/tutor.py`, `tutor/`): `POST /tutor/orgs/{org}/classrooms/{c}/chat`
  (alumnado de la clase o staff; `as=<seudónimo>` = vista previa; `analysis_id` = corrección desde
  la que se abre, que es siempre la primera fuente y debe ser del propio alumno) y
  `GET|POST|DELETE .../documents` (material de la clase, solo staff, `.md`/`.txt`). En la web es un
  **panel lateral (1/3)** que se abre desde una corrección. **Envío al profesorado**:
  `POST|GET .../assignments/{a}/repos/{owner}/shares` (enviar: solo el propio alumno; ver: alumno o
  staff) y `POST .../shares/{id}/read` (staff); la tabla de entregas cuenta las dudas sin leer. Corpus: material de **esa** clase + guía de
  ZuzenAA (`tutor/corpus/*.md`, se indexa al arrancar) + **solo el feedback propio** del alumno.
  Recuperación local (embeddings por hashing, índice en la BD). Responde un **agente**
  (`tutor/agent.py`) con dos herramientas, `buscar_apuntes` y `responder` (salida estructurada:
  explicación, preguntas guía, pasos y apuntes a revisar con motivo; sin código). Proveedor
  remoto de pago por `ZUZENAA_TUTOR_PROVIDER` (`tutor/models.py`): `anthropic` (SDK oficial,
  fallbacks del servidor en los modelos que los admiten) u `openai_compatible` (HTTP); sin clave
  o si falla, el `mock` con la misma estructura. Al proveedor solo llega texto seudonimizado y
  limpio. Si la respuesta trae código se le pide reescribirla una vez y, si insiste, se bloquea.
  Límite de preguntas por usuario y hora. Misma privacidad (seudónimo + limpieza + bloqueo) y
  guardarraíles que el agente. Las conversaciones no se guardan, salvo lo que el alumno envía al profesorado
  (tabla `tutor_shares`, ya limpio: con su seudónimo).
- **Progreso** (`api/progress.py`, `progress/`): `GET .../assignments/{a}/repos/{owner}/progress`
  (progreso del alumno; misma autorización que el histórico) y `GET .../assignments/{a}/progress`
  (evolución de la clase; **solo staff**). Se calcula al leer sobre `analyses` + `git log`; la
  vista de clase **agrega** el progreso de cada alumno (una sola fuente de verdad).
- **Superficie alumno** (`api/me.py`): `GET /me/role` (rol detectado: `staff` si está en el staff
  de alguna clase conocida, `student` si solo tiene entregas, `unknown` si nada; `auth/roles.py`,
  caché 5 min) y `GET /me/assignments` (descubrimiento desde la BD + resumen de progreso por
  entrega; `?as=<seudónimo>&org=&classroom=` = vista previa del profesorado, solo sus clases).
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
  `pseudonyms`, `identity_reveals`, `tutor_documents`, `tutor_chunks`, `tutor_shares`.
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
