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
| `feedback_json` | feedback estructurado (schema del agente) |
| `feedback_md` | render |
| `evolution` | evolución vs. análisis anterior (nullable) |
| `tokens_used` | coste |
| `created_at` | fecha del análisis |
| `forced` | si fue reanálisis forzado |

### `sync_runs` / `analysis_runs` (opcional)
Estado y progreso de las descargas y de los análisis masivos.

## 3. Reglas

- **BD = histórico y metadatos; disco = código.** Ninguno es autoridad de clases/assignments: eso se
  lee de Classroom 50.
- **Portabilidad**: cada assignment guarda `analyses.json` + `feedback.md` en disco.
- **Cache**: por `(repository_id, commit_sha)`; el profesor puede **forzar** reanálisis (se guarda
  como análisis nuevo, no reemplaza el histórico).
- **Retención**: política a definir (repos todo el curso; snapshots comprimidos).
