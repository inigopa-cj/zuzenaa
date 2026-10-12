# Guía de ZuzenAA para el alumnado

## Qué es ZuzenAA

ZuzenAA es la plataforma de evaluación formativa de tu clase. Cada vez que haces push de tu
entrega, ZuzenAA descarga tu código, lo analiza y te deja feedback para mejorar. El feedback
orienta: nunca te da la solución ni código hecho.

## Tu código de alumno

En la plataforma no apareces con tu nombre ni con tu usuario de GitHub. En cada clase tienes
un código, por ejemplo 3.URGAA: tu número de lista seguido de las iniciales de tus apellidos y
de tu nombre. Ese código es siempre el mismo en todas las pantallas de esa clase.

## Mis entregas

En Mis entregas tienes una tarjeta por cada assignment. La insignia de tests indica cuántos
tests de Classroom 50 pasan en tu último commit, y la barra muestra tus puntos. Pulsa Ver mi
progreso para abrir tu ficha con el progreso y el histórico.

## Los tests de Classroom 50

Los tests se ejecutan en GitHub Actions cada vez que haces push. ZuzenAA no los vuelve a
ejecutar: solo lee el resultado. Si un test falla, lee con calma su nombre, porque indica qué
caso espera, y reprodúcelo en tu ordenador antes de volver a subir. Un test que pasaba y deja
de pasar es una regresión: ejecuta todos los tests antes de cada push para no romper lo que ya
funcionaba.

## La pista

Cada análisis incluye una pista con un nivel. La pista te dice dónde mirar, no qué escribir.
Si la misma pista se repite en varias revisiones, es que ese punto sigue sin resolverse:
vuelve a leerla y prueba el caso que menciona.

## Los avisos

Sin análisis: todavía no hay ninguna revisión analizada de esa entrega.
Regresión: tu última revisión rompe tests que antes pasaban.
Pista repetida: la misma pista aparece en tres revisiones seguidas y aún quedan tests.
Sin avance: llevas siete días o más sin commits y todavía quedan tests por pasar.

## Progreso e histórico

En la pestaña Progreso ves un resumen de tu evolución: los puntos de tests en cada revisión,
cuándo empezó a pasar cada test, tu ritmo de commits y los avisos. En la pestaña Histórico
tienes el feedback completo de cada commit, con su fecha.

## Buenas prácticas de trabajo

Haz commits pequeños y frecuentes con mensajes que expliquen el cambio: así es más fácil
encontrar qué se ha roto. Escribe tus propias pruebas para los casos límite, como una entrada
vacía o un valor negativo. Añade un README que explique cómo se ejecuta tu programa.

## El tutor

El tutor responde a tus dudas usando el material de tu clase, tu propio feedback y esta guía.
Siempre te indica de dónde sale cada respuesta. No hace los ejercicios por ti: te orienta para
que llegues tú a la solución.
