# 03 · Flujo de uso y fases

## 1. Flujo completo (profesor)

| Paso | Acción | Dónde |
| --- | --- | --- |
| 1 | Login con GitHub | **Web** (OAuth) |
| 2 | Elegir organización → clase | **Web** (lee de Classroom 50) |
| 3 | Elegir un assignment | **Web** |
| 4 | **Descargar repos** del assignment | **Web** → backend (`git clone`, disco) |
| 5 | **Analizar** (un alumno o todos) | **Web** → backend worker (LLM) |
| 6 | Ver **histórico** por alumno y **progreso** | **Web** (BD + disco) |
| 7 | (Opcional) Forzar reanálisis de un commit | **Web** |

## 2. Flujo completo (alumno)

| Paso | Acción | Dónde |
| --- | --- | --- |
| 1 | Login con GitHub | **Web** (OAuth) |
| 2 | Ver sus clases/assignments | **Web** (BD: lo que el profesor ya descargó/analizó) |
| 3 | Por repo: ver **todo el histórico** de feedback (fecha + commit) y progreso | **Web** |

## 3. Qué sigue ocurriendo en Classroom 50 / GitHub

Todo lo demás del ciclo de vida del ejercicio sigue **fuera** de ZuzenAA:

- Aceptar un assignment (crea el repo del alumno).
- Programar y hacer push (VS Code local).
- **Tests y análisis estático** en GitHub Actions; Release con `result.json`.
- Notas y `scores.json`; regrade; entrega/cierre.
- Crear clases, roster, assignments, tests y plantillas.

ZuzenAA solo **lee** ese estado para saber qué assignments y alumnos hay.

## 4. Pantallas (web)

- **Clases** → lista de clases de la organización.
- **Clase** → assignments; por assignment, botón *Descargar repos*.
- **Assignment**:
  - **Repos**: estado por alumno (descargado / sin cambios / error, último commit).
  - **Análisis**: lanzar individual/masivo, ver progreso.
  - **Histórico**: por alumno, lista de feedbacks (fecha, commit, resumen).
  - **Progreso**: evolución a lo largo del tiempo.
- **Ajustes**: sesión/OAuth/almacenamiento.
- Superficie alumno: mismas entidades filtradas a sí mismo, en **solo lectura**.

## 5. Fases

### Fase R0 — Base
- Nueva BD (`repositories`, `analyses`), `DATA_ROOT` como volumen.
- **Repo Manager**: descarga de repos de un assignment (clon + fetch) con resumen de estado.
- Lectura de Classroom 50 (clases/assignments/roster) para poblar la UI.

**Criterio:** elegir un assignment real y descargar todos sus repos a disco.

### Fase R1 — Agente local + histórico
- Analizar el código local (mock → real), cache por commit, forzar reanálisis.
- Snapshot por análisis + `feedback.md` + `analyses.json`.
- Histórico por alumno y **vista de progreso**.

**Criterio:** analizar un assignment y ver el histórico con fecha y commit.

### Fase R2 — Superficie alumno
- El alumno ve sus clases/assignments y **todo su histórico** y progreso.

**Criterio:** un alumno real ve sus feedbacks ordenados por fecha.

### Fase R3 — Operación
- Análisis masivo como job con progreso y reanudación.
- Presupuesto LLM, retención de disco, compresión de snapshots.
- (Opcional) migración de almacenamiento a MinIO/S3.

### Fase R4 — Mejoras
- Notificaciones (email/Slack) si se decide.
- Analítica por concepto y comparativas entre entregas.

### Fase R5 — Tutor RAG (chatbot)
- **Chatbot de apoyo** en la web que responde dudas sobre ejercicios, teoría y tests, con
  **RAG** (recuperación + generación) sobre el material del curso, no solo con el modelo.
- **Corpus**: enunciados y tests de los assignments (lectura de Classroom 50), material/teoría del
  curso (apuntes, README de plantillas) y, opcionalmente, el **feedback histórico** de ZuzenAA.
- **Ingesta**: trocear e indexar documentos con embeddings; almacén vectorial (p. ej. `pgvector` en
  la propia Postgres) + metadatos por `org`/`clase`/`assignment` para acotar la recuperación.
- **Recuperación**: filtrado por contexto + top-k con reranking; la respuesta **cita** las fuentes
  usadas.
- **Generación**: reutiliza el **gateway LLM** y los **guardarraíles** del agente; el tutor
  **orienta, no resuelve**: no entrega código ni la solución (`agent/guardrails.py`).
- **UI**: panel de chat por assignment; disponible para el **alumno** (dudas) y el **profesor**
  (soporte), con histórico de conversaciones (opcional).
- **Coste y privacidad**: embeddings y respuestas vía el gateway del backend; minimización y
  proveedor UE/local, como en el análisis.

**Criterio:** preguntar «¿por qué falla el test X?» o «explícame Y» y obtener una respuesta con
citas del material, sin código de solución.

**Depende de:** R1 (feedback estructurado), R2 (superficie alumno) y R3 (presupuesto LLM y
operación).

## 6. Pendientes y deudas

Mejoras y deudas **aplazadas a propósito**; no bloquean las fases en curso. Cada una con su fase
objetivo.

### Transversal
- **Proveedor LLM real** detrás del seam (`agent/llm.py: build_provider`): hoy solo `mock`.
  OpenAI/Anthropic/local cuando el resto esté completo; el **contexto real** (árbol + diff) ya se
  le pasa, solo falta el modelo.
- **Contabilidad de coste**: `analyses.tokens_used` existe pero siempre vale 0; registrar tokens/coste.
- **Migraciones**: el esquema se crea con `create_all`; migrar a **Alembic** al estabilizar modelos.
- **Caché de permisos**: la autorización de lectura (staff vs. propio alumno) llama a `gh` en cada
  petición; cachear por `(org, clase)` con TTL.
- **Tests de la web**: hoy solo `oxlint` + `tsc`/`vite build`, sin tests.

### R1 — Agente local + histórico
- **Análisis masivo como job** con progreso y reanudación (hoy es una petición síncrona).
- **Progreso con métricas reales** (tests/notas) cuando haya proveedor; hoy es una traza descriptiva.
- **Evolución más rica**: comparar campos del feedback anterior, no solo un resumen textual.
- **Filas antiguas** sin `feedback_json` estructurado: caen a markdown en crudo en la ficha.

### R2 — Superficie alumno
- El descubrimiento es **desde nuestra BD** (solo lo que el profesor ya descargó/analizó); ampliar a
  roster/teams si el CLI se lo permite al alumno.
- **Paginación** y agrupado por término/sección cuando crezca el histórico.
- **Detección automática de rol** (profesor/alumno) para mostrar la navegación adecuada.

### R3 y R5
- R3: presupuesto LLM, retención y compresión de snapshots, (opcional) almacenamiento MinIO/S3.
- R5: ver **Tutor RAG**.
