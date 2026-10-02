# 04 · Secuencias — Sistema (Repo Manager, agente, evolución)

## 4.1 Repo Manager: clonar y actualizar

```mermaid
sequenceDiagram
  participant B as [BACKEND]
  participant C as [C50/GH] lectura (roster)
  participant G as [C50/GH] repos de alumnos
  participant FS as [DISCO]
  participant DB as [BD]
  B->>C: roster del assignment (owners inscritos)
  C-->>B: lista de owners
  loop por owner
    alt repo no descargado
      B->>G: git clone <clase>-<asig>-<owner>
    else ya existe
      B->>G: git fetch + comprobar nuevo HEAD
    end
    B->>FS: guardar/actualizar repos/<owner>
    B->>DB: registrar head_sha, fecha, estado
  end
```

## 4.2 Agente: análisis local y guardarraíles

```mermaid
sequenceDiagram
  participant B as [BACKEND]
  participant FS as [DISCO]
  participant LLM as [LLM]
  participant DB as [BD]
  B->>FS: leer repos/<owner> en el commit objetivo
  B->>B: construir contexto (diff, evidencias)
  B->>LLM: prompt + contexto
  LLM-->>B: salida estructurada
  B->>B: validar esquema + guardarraíles (sin código/solución)
  alt cumple
    B->>FS: snapshot + feedback.md
    B->>DB: guardar análisis
  else viola
    B->>B: bloquea/regenera; registra el motivo
  end
```

## 4.3 Evolución entre análisis

```mermaid
sequenceDiagram
  participant B as [BACKEND]
  participant DB as [BD]
  participant FS as [DISCO]
  B->>DB: análisis actual + análisis anterior del mismo repo
  DB-->>B: ambos (commit, fecha, feedback)
  B->>FS: diff de código entre ambos commits
  B->>B: comparar y redactar "evolución"
  B->>DB: guardar análisis con campo evolution
```


## Resumen de ubicaciones

| Acción | Ubicación |
| --- | --- |
| Clonar/actualizar repos | `[BACKEND]` → `[DISCO]` |
| Analizar con agente | `[BACKEND]` + `[LLM]` → `[BD]`/`[DISCO]` |
| Guardar histórico y evolución | `[BD]` (+ `feedback.md` en `[DISCO]`) |
| Tests, entrega y notas | `[C50/GH]` (fuera de ZuzenAA) |
