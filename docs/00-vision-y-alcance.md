# 00 · Visión y alcance

## Qué es ZuzenAA

ZuzenAA es una plataforma de **evaluación formativa agéntica** para ejercicios de programación
que se entregan por GitHub con [Classroom 50](https://github.com/foundation50/classroom50).

**Classroom 50 sigue siendo la autoridad** de clases, assignments, entrega, tests y notas.
ZuzenAA **no lo sustituye ni lo reimplementa**: se centra en lo que Classroom 50 no hace.

## Qué añade ZuzenAA

1. **Descargar** al servidor todos los repos de los alumnos de un assignment (clon completo).
2. **Evaluar** ese código local con un **agente** (feedback pedagógico).
3. **Histórico**: todos los feedbacks por alumno, con **fecha y commit**, y **progreso**.
4. **Memoria del curso**: los repos y snapshots quedan archivados en disco, estructurados.
5. **Tutor RAG (futuro)**: un chatbot en la web que resuelve dudas de ejercicios y teoría con
   material del curso citado, sin entregar la solución.

## Reparto de responsabilidades

| Tarea | Responsable |
| --- | --- |
| Clases, roster, assignments, tests, entrega, notas | **Classroom 50** (GitHub) |
| Descargar repos al servidor | **ZuzenAA** (backend) |
| Análisis con el agente y feedback | **ZuzenAA** (backend worker) |
| Histórico de feedback y progreso | **ZuzenAA** (BD + disco) |
| Archivo de entregas del curso | **ZuzenAA** (disco del servidor) |
| Notificar al alumno (futuro) | Opcional (email/Slack) |

Los **tests y el análisis estático siguen en Classroom 50** (GitHub Actions). ZuzenAA **no**
re-ejecuta tests.

## Usuarios

- **Profesor**: elige un assignment, descarga sus repos, lanza el agente y consulta histórico y
  progreso.
- **Alumno**: entra con GitHub y ve sus clases/assignments y **todo su histórico de feedback**.

El feedback **vive solo en la plataforma** (no se publica en GitHub). Notificar por email queda como
mejora futura.

## Principios

1. **No duplicar Classroom 50**: solo lectura de su estado.
2. **El código es la materia prima**: repos locales versionados + snapshots por análisis.
3. **Histórico primero**: cada análisis queda registrado (commit, fecha, feedback, evolución).
4. **Solo orientar**: el agente no entrega código ni solución (guardarraíles).
5. **Coste controlado**: análisis bajo demanda y cache por commit.

## Fuera de alcance

- Re-ejecutar tests o análisis estático localmente (vive en Classroom 50).
- Publicar feedback en GitHub.
- Editor de código en la web.
- Notificaciones automáticas (por ahora).
- Multi-tenant público/SaaS.
