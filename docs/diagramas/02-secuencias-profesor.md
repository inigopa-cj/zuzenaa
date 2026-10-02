# 02 · Secuencias — Profesor

`[C50/GH]` = lo que hace Classroom 50 / GitHub (fuera de ZuzenAA).

## 2.1 Login

```mermaid
sequenceDiagram
  actor P as Profesor
  participant W as [WEB] ZuzenAA
  participant GH as [C50/GH] GitHub OAuth
  participant B as [BACKEND]
  P->>W: Abrir la app
  W->>GH: Autorizar (scopes repo, workflow, read:org)
  GH-->>W: Código
  W->>B: Canjear código
  B->>GH: Solicitar token
  GH-->>B: Token + identidad
  B->>B: Cifrar token y crear sesión
  B-->>W: Sesión + organizaciones
```

## 2.2 Elegir clase y assignment (solo lectura de Classroom 50)

```mermaid
sequenceDiagram
  actor P as Profesor
  participant W as [WEB]
  participant B as [BACKEND]
  participant C as [C50/GH] gh teacher (lectura)
  P->>W: Elige organización y clase
  W->>B: GET /orgs/{org}/classrooms/{c}/assignments
  B->>C: assignment list (lectura)
  C-->>B: assignments de la clase
  B-->>W: lista de assignments
  P->>W: Elige un assignment
```

## 2.3 Descargar repos del assignment

```mermaid
sequenceDiagram
  actor P as Profesor
  participant W as [WEB]
  participant B as [BACKEND]
  participant C as [C50/GH] roster (lectura)
  participant G as [C50/GH] repos de alumnos
  participant FS as [DISCO]
  P->>W: Descargar repos
  W->>B: POST /repos/sync {org, classroom, assignment}
  B->>C: roster (alumnos inscritos)
  C-->>B: owners + repo esperado <clase>-<asig>-<usuario>
  loop por cada alumno
    B->>G: git clone (o fetch si ya existe)
    G-->>B: código + historia
    B->>FS: guardar en <org>/<clase>/<asig>/repos/<owner>
  end
  B-->>W: resumen (descargados / sin cambios / errores)
```

## 2.4 Analizar (uno o todos)

```mermaid
sequenceDiagram
  actor P as Profesor
  participant W as [WEB]
  participant B as [BACKEND]
  participant FS as [DISCO]
  participant LLM as [LLM] proveedor
  participant DB as [BD]
  P->>W: Analizar (alumno / todos)
  W->>B: POST /analysis {scope}
  loop por cada repo objetivo
    B->>FS: leer repo local + diff
    B->>DB: ¿analizado este commit? (cache)
    alt no cacheado o forzar
      B->>LLM: contexto + diff (guardarraíles antes de guardar)
      LLM-->>B: feedback estructurado
      B->>FS: snapshot congelado + feedback.md
      B->>DB: guardar análisis (commit, fecha, evolución)
    end
  end
  B-->>W: resultado / progreso
```

## 2.5 Histórico y progreso

```mermaid
sequenceDiagram
  actor P as Profesor
  participant W as [WEB]
  participant B as [BACKEND]
  participant DB as [BD]
  participant FS as [DISCO]
  P->>W: Abrir un alumno
  W->>B: GET /repos/{...}/analyses
  B->>DB: análisis de ese repo (fecha, commit, feedback)
  DB-->>B: lista
  B->>FS: (opcional) leer feedback.md / snapshot
  B-->>W: histórico + serie de progreso
```
