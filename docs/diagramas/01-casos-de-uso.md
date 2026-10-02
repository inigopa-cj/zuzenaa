# 01 · Casos de uso

Agrupados por **dónde** ocurre cada acción. `ZuzenAA` = nuestra plataforma; `Classroom 50 / GitHub`
= la autoridad de la entrega, los tests y las notas (no lo tocamos).

## A. Profesor — ZuzenAA

```mermaid
flowchart LR
  P([Profesor])
  P --> W1["[WEB] Iniciar sesión (OAuth GitHub)"]
  P --> W2["[WEB] Elegir organización y clase"]
  P --> W3["[WEB] Elegir assignment"]
  W3 --> B1["[BACKEND] Descargar repos del assignment"]
  B1 --> D1["[DISCO] Clonar / actualizar repos"]
  W3 --> B2["[BACKEND] Analizar (un alumno o todos)"]
  B2 --> A1["[AGENTE] Generar feedback + guardarraíles"]
  A1 --> D2["[DISCO] Snapshot + feedback.md"]
  A1 --> BD1["[BD] Guardar análisis (commit, fecha)"]
  W3 --> W4["[WEB] Ver histórico por alumno"]
  W3 --> W5["[WEB] Ver progreso / evolución"]
  W3 --> W6["[WEB] Forzar reanálisis (opcional)"]
```

## B. Alumno — ZuzenAA

```mermaid
flowchart LR
  A([Alumno])
  A --> S1["[WEB] Iniciar sesión (OAuth GitHub)"]
  S1 --> S2["[WEB] Ver sus clases y assignments"]
  S2 --> S3["[WEB] Ver TODO su histórico de feedback (fecha + commit)"]
  S2 --> S4["[WEB] Ver su progreso (solo lectura)"]
```

## C. Profesor y alumno — Classroom 50 / GitHub (fuera de ZuzenAA)

Todo lo demás sigue **en Classroom 50**, no en nuestra plataforma. Se documenta aquí para dejar claro el
reparto.

```mermaid
flowchart LR
  P([Profesor])
  A([Alumno])
  P --> C1["[C50/GH] Crear clases, roster, assignments, tests y plantillas"]
  A --> C2["[C50/GH] Aceptar el assignment (crea su repo)"]
  A --> C3["[LOCAL] Programar en VS Code"]
  C3 --> C4["[C50/GH] git push"]
  C4 --> C5["[C50/GH] Tests en GitHub Actions (Release + result.json)"]
  P --> C6["[C50/GH] Notas, scores.json, regrade, cierre"]
  P --> C7["[C50/GH] Feedback PR / revisión humana"]
```

## Resumen por ubicación

| Ubicación | Naturaleza |
| --- | --- |
| `[WEB]` + `[BACKEND]` | ZuzenAA: elegir, descargar, analizar, histórico, progreso. |
| `[DISCO]` | Repos clonados y snapshots por análisis. |
| `[BD]` | Usuario/sesión/token y los análisis (histórico). |
| `[C50/GH]` | Clases, roster, assignments, tests, entrega, notas y feedback humano. |
| `[LOCAL]` | El alumno programa en VS Code y hace push. |
