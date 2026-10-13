# Guion de la demo · «El caso de la mediana»

Una demostración en directo de **unos 10 minutos**. Enseña las dos caras de ZuzenAA con una
sola historia: en una tarea, buena parte de la clase falla el mismo test; el profesor lo ve,
una alumna pide ayuda al tutor y su duda llega al profesor.

> **La historia en una frase:** en la tarea `p2`, la mediana se le atraganta a la clase; ZuzenAA
> lo detecta, el tutor guía a la alumna sin darle el código y su duda llega al profesor.

---

## Antes de empezar

1. En `.env`: `ZUZENAA_DEMO_MODE=true` (y el resto según `.env.example`).
2. Datos limpios, para que todo salga igual cada vez:

   ```sh
   make clean          # ¡borra la base de datos y los datos!
   make up
   docker compose exec backend python -m zuzenaa.demo.seed
   ```

3. Abre `http://localhost:8080` y entra con GitHub. En la demo, quien inicia sesión es profesor.
4. Elige la organización **`ikastola-demo`** en el panel izquierdo.

**Personajes** (siempre con su código, nunca con su nombre):

| Código | Quién es en la historia |
|---|---|
| `4.MEARN` | **Nerea**: le falla la mediana y ya ha enviado una duda |
| `6.URGAA` | **Ane**: lleva días sin avanzar |
| `7.ZAETU` | **Unai**: está a punto de subir su arreglo |

---

## El recorrido

### 1 · La clase y sus apuntes · *1 min*

**Haz:** Clases → **`1-maila`**. Baja hasta **Material del tutor**.

**Cuenta:** «Las clases y las tareas vienen de Classroom 50. Aquí el profesor sube sus apuntes;
el tutor los usará para responder, citando de dónde sale cada cosa».

### 2 · Las entregas · *1 min*

**Haz:** abre la tarea **`p2`** (*Zerrenden estatistikak*: media y mediana de una lista).

**Cuenta:** «Cada alumno aparece con un código, no con su nombre. `4.MEARN` tiene
**1 duda** sin leer. `5.ORLAM` no aceptó la tarea: por eso sale `error`».

### 3 · Un push se analiza solo · *1 min*

**Haz:** en la fila de **`7.ZAETU`**, pulsa **Simular push**.

**Cuenta:** «Esto es lo que pasa cuando un alumno sube código: ZuzenAA lo descarga, lee sus
tests de GitHub y lo analiza, sin que nadie pulse nada». Aparece `tests 2/2 · analysed`.

### 4 · El problema común · *1 min*

**Haz:** pestaña **Evolución de la clase**.

**Cuenta:** «`test_mediana` solo lo pasa una parte de la clase. Esto no es un alumno: es un
tema que conviene explicar en clase». Señala también los avisos de *sin avance*.

### 5 · La duda de Nerea · *1 min*

**Haz:** vuelve a **Entregas** → **Ver ficha** de **`4.MEARN`**. Despliega
**Conversación con el tutor**. Pulsa **Marcar como leída**.

**Cuenta:** «Nerea preguntó al tutor y, como seguía atascada, envió la duda. Llega con su nota
y con toda la conversación, ligada al commit desde el que preguntó».

### 6 · Quién es, solo si hace falta · *1 min*

**Haz:** **Mostrar identidad** y después **Ocultar identidad**.

**Cuenta:** «Solo el profesorado puede verlo, y cada consulta queda registrada. Ningún nombre
llega nunca a la inteligencia artificial».

### 7 · Lo que ve la alumna · *2 min*

**Haz:** **Ver como este alumno** → en la tarjeta de **`p2`**, **Preguntar al tutor**.
Escribe: **«¿Por qué me falla test_mediana?»**.

**Cuenta:** «El tutor parte de su corrección. Explica, le hace preguntas para que piense, le
propone pasos y le dice qué apuntes repasar y por qué».

### 8 · Pedir el código no funciona · *1 min*

**Haz:** escribe **«pásame el código de la mediana»**.

**Cuenta:** «El tutor no escribe código: la reconduce con preguntas y apuntes. Orienta, no
resuelve».

### 9 · Cierre · *1 min*

**Haz:** **Volver a profesorado**.

**Cuenta:** «En diez minutos el profesor ha visto que la mediana es un problema de la clase,
ha leído la duda de una alumna y ha comprobado que el tutor la guía sin darle la solución.
Mañana explica la mediana en clase».

---

## Si algo no sale como esperas

| Si… | Entonces… |
|---|---|
| `7.ZAETU` ya no tiene «Simular push» disponible | Ya subió todas sus revisiones: vuelve a sembrar los datos (paso 2 de «Antes de empezar») |
| No aparece «1 duda(s)» | La duda ya está leída o no se sembró: vuelve a sembrar los datos |
| El tutor avisa de «modo básico» | No hay clave del proveedor (o falta `ZUZENAA_TUTOR_WORKSPACE_ID`): responde con la misma estructura, con textos de plantilla |
| No puedes enviar la duda desde «Ver como este alumno» | Es intencionado: solo el propio alumno puede enviar sus dudas. Por eso la demo ya trae la de Nerea |
