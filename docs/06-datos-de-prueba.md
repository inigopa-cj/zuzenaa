# 06 · Datos de prueba (modo demo)

ZuzenAA lee el estado real de Classroom 50 desde GitHub. Para **ver la plataforma
funcionando sin tocar GitHub** (demos, desarrollo de la web, pruebas manuales) existe
el **modo demo**: un dataset ficticio que emula Classroom 50 en local.

> ⚠️ **Nunca** actives el modo demo en producción. Sustituye el CLI `gh` por un
> emulador in-process y apunta el clonado a repos locales.

## Qué emula

| Pieza | Real | Modo demo |
|---|---|---|
| Orgs / clases / assignments / roster / staff | `gh teacher` + API de GitHub | `demo/gh_runner.py` (mismo JSON por stdout) |
| Repos de los alumnos | `https://github.com/<org>/<repo>.git` | repos git locales en `<DATA_ROOT>/demo-origins/` |
| Tests (GitHub Actions → Release con `result.json`) | Actions del repo del alumno | releases ficticias en `<DATA_ROOT>/demo-releases/` |
| Push del alumno | `git push` desde su equipo | «Simular push» (web) o `python -m zuzenaa.demo.push` |
| Análisis | agente real (proveedor `mock` por defecto) | igual, con fechas de commit reales |

El dataset (`demo/dataset.py`) es la **única fuente de verdad** y no hace I/O:

- Org `ikastola-demo`, con una clase activa `1-maila` y otra archivada `2-maila`.
- Dos assignments: `p1` (abierta) y `p2` (cerrada).
- Seis alumnos con entregas en estados distintos: varias revisiones analizadas,
  revisiones pendientes, una entrega sin analizar y una **no aceptada** (fila `error`).
- Cada entrega es una secuencia de commits (deltas acumulativos) para que el agente
  pueda calcular el **diff** entre revisiones.

## Cómo activarlo

1. En `.env`:

   ```sh
   ZUZENAA_DEMO_MODE=true
   # El clonado apunta a los orígenes locales (lo normal es dejar el valor por defecto
   # del modo demo; se muestra para que quede explícito).
   ZUZENAA_GIT_CLONE_URL_TEMPLATE=file:///data/demo-origins/{org}/{repo}
   ```

2. Arranca el stack y siembra el dataset (dentro del contenedor del backend):

   ```sh
   make up
   docker compose exec backend python -m zuzenaa.demo.seed
   ```

   El seed es **idempotente**: reconstruye los orígenes y reutiliza los análisis ya
   existentes (mismo commit ⇒ `cached`).

3. Entra en la web (`http://localhost:8080`, o el puerto de `ZUZENAA_WEB_PORT`) e
   inicia sesión con GitHub. En la demo, **cualquier login es staff** de la clase, así
   que verás la superficie de profesorado completa.

## Qué se puede ver

- **Profesorado**: elegir `ikastola-demo` → `1-maila` → `p1`/`p2` → descargar repos →
  analizar → histórico y progreso por alumno, y pestaña **Evolución de la clase**.
- **Alumnado**: quien inicia sesión es staff de la demo, **salvo** los alumnos del dataset
  (`ane-urrutia`, `nerea-mendia`…): entrando como uno de ellos se ve la superficie del alumno
  (**Mis entregas**). Sin cuentas de GitHub para ellos, lo más cómodo es **«Ver como este
  alumno»** desde su ficha.
- **Estados variados**: la entrega no aceptada de Maialen aparece como `error`; las
  revisiones pendientes se pueden analizar en vivo pulsando «Analizar».

## Simular un push (commit para pasar los tests)

Reproduce el ciclo completo de una entrega sin tocar GitHub:

1. El alumno hace **commit + push** de su siguiente revisión del *track* (el código con
   el que intenta pasar los tests).
2. «GitHub Actions» corre los tests y publica la **release** con `result.json`
   (qué tests pasan y cuántos puntos). ZuzenAA **no ejecuta** los tests: solo lee ese
   resultado, igual que haría con Classroom 50.
3. ZuzenAA **descarga** el repo y lo **analiza automáticamente**. El feedback mock comenta
   los tests (cuántos pasan, si mejora o empeora respecto a la revisión anterior y una
   pista sobre el primero que falla, sin dar la solución).

Desde la web: en la tabla del assignment, **«Simular push»** en la fila del alumno (solo
aparece en modo demo). Desde la terminal:

```sh
docker compose exec backend python -m zuzenaa.demo.push p1 jone-larrea
```

Cada push añade el siguiente commit del track; cuando no quedan revisiones responde
con un error `409`. Los resultados de tests de cada revisión están en
`demo/dataset.py` (`TESTS` y `TRACK_PASSING`). Para volver al estado inicial, vuelve a
ejecutar el seed.

> El formato del `result.json` de la demo es propio de ZuzenAA
> (`github/results.py: TestResults`). El lector real de las releases de Classroom 50 está
> **pendiente** de verificar su formato; fuera del modo demo el análisis sigue sin tests.

## Ver el progreso y la evolución de la clase

Haz varios «Simular push» seguidos a distintos alumnos (p. ej. `jone-larrea` y `ekain-agirre` en
`p1`): cada push añade un punto a la curva de tests de su ficha (pestaña **Progreso**) y mueve la
media diaria y la tasa por test de la pestaña **Evolución de la clase** del assignment.

## Cómo desactivarlo

```sh
ZUZENAA_DEMO_MODE=false
```

Vuelve a `gh` real y a `https://github.com/...`. Los datos sembrados viven en el
volumen `data`; `make clean` los borra junto con la base de datos.

## Detalles de implementación

- `demo/dataset.py` — el mundo ficticio (fixtures con la forma exacta de `gh`).
- `demo/gh_runner.py` — runner in-process que se inyecta en `GhCli(runner=...)` cuando
  `ZUZENAA_DEMO_MODE=true` (`api/deps.py: get_gh_cli`). Solo emula los comandos que usa
  ZuzenAA; cualquier otro falla con código 1, como `gh` sin red.
- `demo/seed.py` — fabrica los repos git locales, los clona con el código real de
  producción (`repos.service.sync_assignment`) y analiza las revisiones ya entregadas
  fechando cada análisis en su commit (`analyze_repository(..., created_at=...)`).
- `demo/releases.py` — releases ficticias (`result.json` por commit) que lee
  `github/results.py: load_test_results`.
- `demo/push.py` — push simulado: commit en el origen → release → descarga → análisis.
  Expuesto en `POST /demo/orgs/{org}/classrooms/{c}/assignments/{a}/repos/{owner}/push`
  (404 fuera del modo demo).
- `demo/__init__.py` — `origins_root()` y `clone_url_template()` (plantilla `file://`).