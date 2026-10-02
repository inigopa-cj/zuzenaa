# Contribuir a ZuzenAA

Gracias por el interés. Esta guía resume cómo montar el entorno, los comandos de calidad y las
convenciones del proyecto.

## Puesta en marcha

La vía recomendada es **Docker** (db + backend + web). Ver el [README](README.md) y la
[guía de configuración](docs/05-guia-configuracion.md).

Para desarrollo **sin Docker**:

- **Backend** (Python 3.12, gestionado con [`uv`](https://docs.astral.sh/uv/)):
  ```sh
  cd backend
  uv sync
  uv run uvicorn zuzenaa.main:app --reload
  ```
- **Web** (Node.js 24):
  ```sh
  cd web
  npm install
  npm run dev     # proxy /api -> VITE_API_PROXY
  ```

## Calidad antes de enviar

```sh
make test       # backend: ruff + mypy + pytest
make test-web   # web: oxlint + build
make test-all   # ambos
```

- **Backend**: `ruff` (lint, línea 100), `mypy` en modo **strict**, `pytest`.
- **Web**: `oxlint` y `tsc`/`vite build`.
- El CI (`.github/workflows/ci.yml`) ejecuta lo mismo en cada push/PR.

## Convenciones

- Textos de UI y documentación en **castellano**, en voz activa y en minúsculas de frase.
- **Sin comentarios** en el código salvo que aporten contexto no evidente.
- Respeta la arquitectura: la web habla con el backend por `/api`; el backend lee Classroom 50
  **solo** a través del adaptador `gh` (`backend/src/zuzenaa/github/`) y nunca re-ejecuta tests.
- El agente no publica en GitHub ni entrega la solución: pasa por los **guardarraíles**
  (`agent/guardrails.py`).

## Estructura (backend)

```
backend/src/zuzenaa/
├── api/        # endpoints FastAPI (auth, orgs, repos, analyses, me)
├── agent/      # worker, contexto real, proveedores LLM, guardarraíles
├── github/     # adaptador de solo lectura sobre el CLI gh
├── repos/      # clon/fetch local, rutas en disco
├── db/         # modelos y sesión SQLAlchemy
└── auth/       # OAuth de GitHub y cifrado de tokens
```

## Flujo de trabajo

1. Crea una rama: `feat/...`, `fix/...`, `docs/...`.
2. Haz commits pequeños y con mensaje en imperativo (p. ej. `añade autorización al histórico`).
3. Asegúrate de que `make test-all` pasa.
4. Abre un PR rellenando la plantilla y describe el cambio y cómo probarlo.

## Qué no subir

- `.env` ni secretos.
- Datos de alumnado: repos descargados, snapshots, volcados de BD.
- Artefactos generados (`.venv/`, `node_modules/`, caches, `*.db`): ya están en `.gitignore`.

## Licencia

Al contribuir aceptas que tu aportación se publique bajo la **GPL-3.0** de este repositorio
(ver [`LICENSE`](LICENSE)).
