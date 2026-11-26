# Prueba manual en AI Studio

Objetivo: comprobar, antes de programar nada, si Gemini devuelve el detalle segundo a segundo
que el proyecto necesita, o si se queda en un resumen.

**Canal base elegido:** @AsíPaso.

## Por qué se prueba un solo bloque de 60 segundos

Gemini acepta un millón de fichas de entrada pero solo escribe hasta 64 000. Un video de diez
minutos con los once aspectos de la especificación pasaría de 80 000 fichas de salida, así que
el modelo no tiene espacio y resume. Un bloque de 60 segundos cabe de sobra, y al caber no hay
motivo para comprimir.

Si esta prueba devuelve 60 entradas completas, el método sirve y se programa. Si devuelve menos
de 60 o agrupa segundos, hay que bajar el bloque a 30 segundos. Cualquiera de los dos
resultados es información útil.

## Pasos

1. Abrir `aistudio.google.com` e iniciar sesión con la cuenta de Google.
2. Elegir el modelo Flash más reciente de la lista (3.8 Flash o 3 Flash).
3. Insertar el enlace de YouTube del video de @AsíPaso.
4. Activar la salida estructurada (*Structured output*) y pegar el esquema de abajo.
5. Si hay un control de razonamiento (*Thinking*), bajarlo al mínimo. El razonamiento consume
   el mismo presupuesto que la salida, y si se lo come todo la respuesta llega vacía sin avisar.
6. Pegar la instrucción de abajo y ejecutar.
7. Copiar el JSON del resultado.

## La instrucción

```
Eres un analista de edición de video. Analiza ÚNICAMENTE los primeros 60 segundos
del video, del segundo 0 al 59.

Devuelve una entrada por CADA segundo: sesenta entradas exactas, de la 0 a la 59.
No omitas ningún segundo. No agrupes varios segundos en una sola entrada.
No resumas, no expliques, no añadas conclusiones ni introducción. Solo rellena los campos.

Para cada segundo:
- s: el número de segundo, de 0 a 59.
- pantalla: qué se ve exactamente en ese segundo. Concreto: quién aparece, dónde está,
  qué hace. No vale "escena de la película".
- corte: "corte" si en ese segundo cambia el plano, "transicion" si hay una transición
  (fundido, desenfoque, barrido), "ninguno" si sigue el mismo plano.
- plano: primer plano, plano medio, plano general, detalle, picado, contrapicado u otro.
- narracion: las palabras exactas que se oyen en ese segundo. Si no se habla, cadena vacía.
- texto_en_pantalla: el texto escrito que aparece, tal cual. Si no hay, cadena vacía.
- meme_o_sticker: qué meme o sticker aparece y en qué zona de la pantalla.
  Si no hay, cadena vacía.
- sonido: música, efecto de sonido concreto, o "silencio".
- energia_voz: de 1 a 5, cuánta energía tiene la voz del narrador en ese segundo.
  1 es casi un susurro, 5 es un grito.

Si algo no se puede determinar, escribe "no se distingue". Nunca dejes un campo fuera.
```

## El esquema de salida

```json
{
  "type": "object",
  "properties": {
    "bloque": { "type": "string" },
    "segundos": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "s": { "type": "integer" },
          "pantalla": { "type": "string" },
          "corte": { "type": "string", "enum": ["corte", "transicion", "ninguno"] },
          "plano": { "type": "string" },
          "narracion": { "type": "string" },
          "texto_en_pantalla": { "type": "string" },
          "meme_o_sticker": { "type": "string" },
          "sonido": { "type": "string" },
          "energia_voz": { "type": "integer" }
        },
        "required": [
          "s", "pantalla", "corte", "plano", "narracion",
          "texto_en_pantalla", "meme_o_sticker", "sonido", "energia_voz"
        ]
      }
    }
  },
  "required": ["bloque", "segundos"]
}
```

## Qué mirar en el resultado

| Pregunta | Qué significa |
|---|---|
| ¿Llegaron 60 entradas? | Si sí, el bloque de 60 s es el tamaño correcto |
| ¿El campo `pantalla` es concreto o genérico? | Si es genérico, hay que exigir más en la instrucción |
| ¿Los cortes coinciden con lo que se ve? | Es la medida que más importa para copiar el ritmo |
| ¿La narración está transcrita literal? | Si no, se transcribe aparte y se cruza por tiempos |
| ¿Detectó memes y textos en pantalla? | Decide si lo visual se automatiza o se llena a mano |

## Estado

- [x] Instrucción y esquema preparados
- [ ] Jhon ejecuta la prueba y devuelve el JSON
- [ ] Decisión: tamaño de bloque definitivo y qué aspectos se automatizan
