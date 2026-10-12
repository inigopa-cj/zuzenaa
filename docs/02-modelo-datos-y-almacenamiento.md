# 02 · Modelo de datos y almacenamiento

## 1. Estructura en disco

```
DATA_ROOT/                              # volumen Docker, p.ej. /data
  <org>/
    <classroom>/
      <assignment>/
        repos/
          <owner>/                       # clon git completo (con historia)
            .git/
        snapshots/
          <owner>/
            <UTC-fecha>-<short-sha>/     # copia congelada del código analizado
              feedback.md                # feedback renderizado de ese análisis
        analyses.json                    # índice de análisis (portabilidad)
```

- **`repos/<owner>`**: clon normal; se actualiza con `git fetch` en cada descarga.
- **`snapshots/<owner>/<fecha>-<sha>`**: se crea en cada análisis; es la evidencia archivada.
- **`feedback.md`**: copia legible, para que el histórico no dependa solo de la BD.
- **`analyses.json`**: índice de análisis (commit, fecha, resumen), exportable.

Los nombres (`owner`, `classroom`, `assignment`) se normalizan (`[a-z0-9-]`, minúsculas) para evitar
rutas inseguras.

## 2. Base de datos (PostgreSQL)

### `users`
| Campo | Notas |
| --- | --- |
| `id` | PK |
| `github_id`, `login`, `name`, `avatar_url` | identidad |
| `encrypted_token` | token de GitHub cifrado (Fernet) |
| `created_at`, `updated_at` | epoch |

### `sessions`
`id` (PK, token de sesión), `user_id` (FK), `created_at`, `expires_at`.

### `oauth_states`
`state` (PK), `created_at`.

### `repositories`
Un repo de alumno descargado.
| Campo | Notas |
| --- | --- |
| `id` | PK |
| `org`, `classroom`, `assignment`, `owner` | clave lógica (única) |
| `repo_full_name` | `<org>/<clase>-<asig>-<owner>` |
| `path` | ruta local del clon |
| `default_branch`, `head_sha`, `head_committed_at` | último commit visto |
| `last_synced_at` | última descarga |
| `status` | ok / missing / error |
| `detail` | último error |

### `analyses`
Un análisis (feedback) sobre un commit.
| Campo | Notas |
| --- | --- |
| `id` | PK |
| `repository_id` | FK repositories |
| `commit_sha`, `commit_committed_at` | commit analizado |
| `snapshot_path` | carpeta del snapshot |
| `provider` | mock/openai/… |
| `feedback_json` | feedback estructurado (schema del agente) + `tests` (resultado de los tests del commit, si lo hay) |
| `feedback_md` | render |
| `evolution` | evolución vs. análisis anterior (nullable) |
| `tokens_used` | coste |
| `created_at` | fecha del análisis |
| `forced` | si fue reanálisis forzado |

### `pseudonyms`
Seudónimo estable de cada alumno **por clase** (ver docs/01 §4.1).
| Campo | Notas |
| --- | --- |
| `org`, `classroom`, `login` | únicos juntos; `login` en minúsculas, nunca sale del backend |
| `position` | n.º en la lista de clase (fijado la primera vez; únicos por clase) |
| `alias` | `<posición>.<AP1><AP2><N>`, p. ej. `3.URGAA` (único por clase) |
| `encrypted_name` | `nombre|apellidos` cifrado (Fernet de `ZUZENAA_SECRET_KEY`) |

### `identity_reveals`
Registro de cada «Mostrar identidad»: `org`, `classroom`, `alias`, `viewer_login`, `created_at`.

### `tutor_documents` / `tutor_chunks`
Corpus del tutor. `tutor_documents`: `org`/`classroom` (vacíos en la guía de ZuzenAA), `source`
(`material` | `zuzenaa`), `title`, `filename`, `content_hash`, `uploaded_by`, `chunk_count`.
`tutor_chunks`: fragmentos (`heading`, `text`) con su `embedding` en JSON. La similitud se calcula
en el backend; si el corpus crece, el paso natural es `pgvector` en la misma Postgres.
El feedback del alumno **no** se copia aquí: se recupera en cada pregunta y solo el suyo.

### `tutor_shares`
Dudas que el alumno **envía a su profesorado** desde el tutor, ligadas a una corrección: `org`,
`classroom`, `assignment`, `owner` (login, solo backend), `analysis_id`, `note`, `transcript`
(JSON `[{role, text}]`), `created_at`, `read_at`, `read_by`. Nota y conversación se guardan **ya
limpias** de datos personales (seudónimo). Es lo único del tutor que se guarda.

### `sync_runs` / `analysis_runs` (opcional)
Estado y progreso de las descargas y de los análisis masivos.

### Progreso y evolución de la clase (sin tabla propia)
Se **calculan al leer** a partir de `analyses` (feedback + `tests`) y del `git log` del clon
(`progress/`). No se persisten: siempre están al día y no duplican el histórico. Cuando un LLM real
redacte los resúmenes, se cachearán por `(repository_id, último análisis incluido)`.

## 3. Reglas

- **BD = histórico y metadatos; disco = código.** Ninguno es autoridad de clases/assignments: eso se
  lee de Classroom 50.
- **Portabilidad**: cada assignment guarda `analyses.json` + `feedback.md` en disco.
- **Cache**: por `(repository_id, commit_sha)`; el profesor puede **forzar** reanálisis (se guarda
  como análisis nuevo, no reemplaza el histórico).
- **Retención**: política a definir (repos todo el curso; snapshots comprimidos).
