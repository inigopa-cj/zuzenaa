# Diagramas

Diagramas del uso actual de ZuzenAA: **casos de uso** y **secuencia**, indicando **dónde** ocurre
cada acción y, en particular, **qué se hace en Classroom 50** (que sigue siendo la autoridad de la
entrega, los tests y las notas).

| Doc | Contenido |
| --- | --- |
| [`01-casos-de-uso.md`](01-casos-de-uso.md) | Casos de uso agrupados por ubicación. |
| [`02-secuencias-profesor.md`](02-secuencias-profesor.md) | Descargar repos, analizar, histórico y progreso. |
| [`03-secuencias-alumno.md`](03-secuencias-alumno.md) | Login, ver histórico y entrega (en Classroom 50). |
| [`04-secuencias-sistema.md`](04-secuencias-sistema.md) | Repo Manager, agente, snapshots y evolución. |

## Convenciones

- **Lenguaje:** Mermaid (render nativo en GitHub y editores markdown).
- **Etiquetas de ubicación** (en el nombre del participante/agrupación):

| Etiqueta | Significado |
| --- | --- |
| `[WEB]` | Aplicación ZuzenAA (React). |
| `[BACKEND]` | API FastAPI; único que habla con GitHub y el LLM. |
| `[DISCO]` | Almacenamiento del servidor (repos y snapshots). |
| `[BD]` | PostgreSQL de ZuzenAA (histórico y estado). |
| `[LLM]` | Proveedor de modelo (externo o local). |
| `[C50/GH]` | **Classroom 50 / GitHub**: autoridad de clases, assignments, entrega, tests y notas. |
| `[LOCAL]` | Equipo del alumno (VS Code) o el profesor. |

Cuando un paso ocurre en `[C50/GH]`, se anota explícitamente porque **no** es ZuzenAA quien lo hace.
