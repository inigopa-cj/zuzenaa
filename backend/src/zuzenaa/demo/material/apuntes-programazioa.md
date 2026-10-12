# Apuntes de Programazioa I

## Leer números del teclado

La función input siempre devuelve texto. Para operar con números hay que convertir ese texto
con int o float. Si el usuario escribe algo que no es un número, la conversión lanza un
ValueError: captúralo con try y except y decide qué hacer, por ejemplo avisar al usuario y
devolver None.

## Entradas incorrectas

Un buen programa no se rompe con entradas inesperadas. Piensa qué pasa si el usuario escribe
letras, deja la entrada vacía o mete un número negativo. Los tests de sarrera okerra (entrada
incorrecta) comprueban justo eso: que tu programa avise sin terminar con un error.

## Argumentos de la línea de comandos

Con el módulo argparse tu programa puede recibir los datos al ejecutarse en lugar de pedirlos
con input. Así es más fácil probarlo de forma automática: el test llama a la función main con
una lista de argumentos y comprueba el código de salida.

## La media de una lista

La media es la suma de los elementos dividida entre la cantidad de elementos. Antes de dividir
comprueba si la lista está vacía: dividir entre cero provoca un ZeroDivisionError. Decide qué
debe devolver tu función en ese caso y escríbelo en su docstring.

## La mediana

La mediana es el valor central de la lista una vez ordenada. Si la lista tiene un número impar
de elementos, es el del medio. Si tiene un número par, es la media de los dos valores centrales.
No ordenes la lista original: trabaja con una copia ordenada.

## Valores máximo y mínimo

Para el máximo y el mínimo puedes recorrer la lista guardando el mejor valor visto hasta ahora.
Igual que con la media, decide qué ocurre con una lista vacía.

## Probar con pytest

Cada test es una función cuyo nombre empieza por test_ y que usa assert para comprobar un
resultado. Ejecuta pytest en tu ordenador antes de cada push. Cuando compares números
decimales, usa pytest.approx para evitar errores de redondeo.
