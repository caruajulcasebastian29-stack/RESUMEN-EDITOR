# Análisis en dos niveles

Corrección al plan, salida de una pregunta de Jhon: si el video se analiza en bloques sueltos
de un minuto, ¿qué pasa con el resto de la historia?

## El problema

La pasada por bloques es obligatoria por el techo de salida: Gemini acepta un millón de fichas
de entrada pero escribe como máximo 64 000. Un video de 22 minutos son 1 342 segundos, y una
fila por segundo con nueve campos pasa de 130 000 fichas de respuesta. No cabe, y cuando no
cabe el modelo resume.

Pero los bloques tienen un punto ciego real: **el bloque 14 no sabe qué pasó en el bloque 3.**

- Para la **edición** da igual. Dónde cortan, cuánto dura cada plano, cada cuánto entra un
  meme, cuándo sube la voz: son hechos locales, visibles en el segundo en que ocurren.
- Para la **trama** no da igual. Dónde está el giro, cómo se construye la intriga, qué se
  cuenta y qué se salta, cómo cierran: eso solo se ve mirando el conjunto.

## La solución: dos pasadas sobre el mismo video

| | Pasada de detalle | Pasada de conjunto |
|---|---|---|
| **Cómo** | 23 bloques de 60 s, uno por llamada | El video entero en una sola llamada |
| **Resolución** | Alta | Baja |
| **Coste** | ~6 000 fichas de entrada por bloque | ~140 000 fichas, una sola vez |
| **Salida** | Una fila por segundo | Una ficha de estructura |
| **Qué saca** | Cortes, planos, narración literal, textos en pantalla, memes y stickers, sonido, energía de la voz | Fin del gancho, punto del giro, qué se cuenta y qué se salta, tipo de cierre, reparto de los chistes a lo largo del video |
| **¿Resumir está bien?** | No. Resumir aquí es el fallo que se quiere evitar | Sí. Aquí se pide la forma del conjunto, no el segundo a segundo |

Los 22 minutos se recorren enteros en las dos pasadas. Ningún tramo queda sin analizar.

## Continuidad entre bloques

Además, cada bloque recibe como contexto las dos últimas frases narradas del bloque anterior.
No sirve para la trama —para eso está la pasada de conjunto— pero evita que la ficha corte una
frase por la mitad y que se pierda el enlace entre escenas.

## Orden de ejecución por video

1. Pasada de conjunto. Barata y rápida, y da el mapa: dónde está el gancho, el giro y el cierre.
2. Pasada de detalle, los 23 bloques, usando ese mapa para etiquetar cada bloque según la parte
   de la historia en la que cae.
3. Las dos se funden en una sola ficha de video.

Hacerlo en este orden importa: con el mapa delante, la pasada de detalle puede anotar si el
segundo que está describiendo pertenece al gancho, al desarrollo, al giro o al cierre. Al revés
no se puede.
