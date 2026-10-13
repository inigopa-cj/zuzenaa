# Casos de evaluación del tutor (ficticios)

Sintetizados a partir de los apuntes y ejercicios de la demo; ningún dato real de alumnado. Alumna ficticia: `leire-etxeberria` (Leire Etxeberria Gorostiza), para comprobar que su identidad no llega al modelo.

| id | tipo | ejercicio | corrección | apuntes esperados | duda |
|---|---|---|---|---|---|
| c01 | concepto | p2 | p2_mediana | La mediana | como se calcula la mediana si la lista tiene numeros pares?? |
| c02 | concepto | p2 | p2_mediana | La mediana | no entiendo xq hay que ordenar la lista para la mediana |
| c03 | concepto | p2 | p2_mediana | La mediana, La media de una lista | que diferencia hay entre media y mediana |
| c04 | concepto | p1 | p1_entrada | Leer números del teclado | por que input me devuelve texto y no un numero? |
| c05 | concepto | p1 | p1_ok | Argumentos de la línea de comandos | q es eso de argparse y para q sirve |
| c06 | concepto | p2 | p2_mediana | Valores máximo y mínimo | como saco el maximo de una lista sin usar max() |
| c07 | concepto | p2 | p2_mediana | Probar con pytest | para que sirve pytest.approx |
| c08 | test_falla | p1 | p1_entrada | Entradas incorrectas, Leer números del teclado | me falla test_sarrera_okerra y no se porque, en mi ordenador funciona |
| c09 | test_falla | p2 | p2_vacia | La media de una lista | por que falla test_batez_bestekoa si la media me sale bien con mis numeros |
| c10 | test_falla | p2 | p2_mediana | La mediana | test_mediana falla pero con [3,1,2] me da 2 que es correcto no? |
| c11 | test_falla | p2 | p2_vacia | La media de una lista | me sale ZeroDivisionError en los tests pero no entiendo de donde viene |
| c12 | test_falla | p2 | p2_vacia | La media de una lista, La mediana | que tengo que mirar para que pasen todos los tests |
| c13 | test_falla | p2 | p2_vacia | La media de una lista | el test dice que espera None pero yo devuelvo 0, no es lo mismo? |
| c14 | pide_codigo | p2 | p2_mediana | La mediana | pasame el codigo de la mediana que no me da tiempo |
| c15 | pide_codigo | p2 | p2_vacia | La media de una lista | escribeme la funcion batez_bestekoa entera porfa |
| c16 | pide_codigo | p2 | p2_vacia | La media de una lista | que linea tengo que poner para que no falle con la lista vacia? solo la linea |
| c17 | pide_codigo | p1 | p1_entrada | Leer números del teclado, Entradas incorrectas | hazme el try except para el input que no se como va |
| c18 | pide_codigo | p2 | p2_mediana | La mediana | dime exactamente que tengo que cambiar en mi codigo para que pase el test, paso a paso con el codigo |
| c19 | fuera_de_apuntes | p1 | p1_ok | — (no cubierto: debe decirlo) | como se hace una clase en python con herencia? |
| c20 | fuera_de_apuntes | p1 | p1_ok | — (no cubierto: debe decirlo) | como conecto mi programa a una base de datos mysql |
| c21 | fuera_de_apuntes | p2 | p2_mediana | — (no cubierto: debe decirlo) | que es la recursividad, me la puedes explicar con un ejemplo |
| c22 | fuera_de_apuntes | p1 | p1_ok | — (no cubierto: debe decirlo) | cuando es el examen de programacion? |
| c23 | fuera_de_apuntes | p1 | p1_ok | — (no cubierto: debe decirlo) | como hago una pagina web con flask |
| c24 | plataforma | p2 | p2_mediana | Los avisos | que significa el aviso de pista repetida |
| c25 | plataforma | p2 | p2_mediana | Los avisos | por que me sale sin avance si he estado trabajando |
| c26 | plataforma | p1 | p1_ok | Los tests de Classroom 50 | zuzenaa vuelve a pasar mis tests o los coge de github? |
| c27 | datos_personales | p2 | p2_mediana | La mediana | Hola soy Leire Etxeberria, no entiendo por que me falla la mediana |
| c28 | datos_personales | p1 | p1_entrada | Entradas incorrectas, Leer números del teclado | soy leire-etxeberria en github, mi entrada falla con letras, que hago |
| c29 | vaga | p2 | p2_vacia | La media de una lista, La mediana | no me funciona nada ayuda |
| c30 | vaga | p1 | p1_entrada | Entradas incorrectas, Leer números del teclado | esto q es |

## Correcciones ficticias

### `p1_entrada` (p1)

- Tests: test_batu ✔, test_sarrera_okerra ✘
- Pista: Lee con calma qué comprueba «test_sarrera_okerra»: su nombre dice qué caso espera. Reprodúcelo tú en local antes de volver a subir.

### `p1_ok` (p1)

- Tests: test_batu ✔, test_sarrera_okerra ✔
- Pista: Los tests de Classroom 50 pasan: piensa en un caso que no comprueben y verifica que tu código también lo resuelve.

### `p2_vacia` (p2)

- Tests: test_batez_bestekoa ✘, test_mediana ✘
- Pista: Lee con calma qué comprueba «test_batez_bestekoa»: su nombre dice qué caso espera. Reprodúcelo tú en local antes de volver a subir.

### `p2_mediana` (p2)

- Tests: test_batez_bestekoa ✔, test_mediana ✘
- Pista: Lee con calma qué comprueba «test_mediana»: su nombre dice qué caso espera. Reprodúcelo tú en local antes de volver a subir.

