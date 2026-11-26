# Voces

Requisitos: expresiva, carismática, que conecte, gratuita, con derecho a usarla en el canal,
y un catálogo final de máximo cuatro.

## Corrección del enfoque

La primera versión de este documento proponía **elegir** voces de un catálogo (Charon, Puck,
Orus). Estaba mal planteado. Esas son voces de stock: correctas, neutras y olvidables, y por
eso el resultado sonaba a lector automático y no a narrador.

Lo que hace falta es lo contrario: **diseñar el personaje de voz describiéndolo con palabras**
—edad, timbre, textura, acento, carácter, manías al hablar— y dejar que el modelo lo
construya. Es una función que ya existe en varias herramientas y se llama *voice design*.
La descripción es la mitad del resultado; la otra mitad es la nota de actuación.

Los diez personajes diseñados están en la hoja de diseño de voz, con la descripción lista
para pegar.

---

## 1. Dónde diseñar y escuchar (gratis)

| Herramienta | Qué da | Derecho a monetizar |
|---|---|---|
| **Speechma** — empezar aquí | Diseño por descripción, sin cuenta ni tarjeta, español, hasta 1000 caracteres por generación | Gratis; conviene revisar sus términos antes de publicar |
| **ElevenLabs Voice Design v3** | El diseñador más expresivo que existe hoy; admite marcas como `[susurra]`, `[se ríe]`, `[suspira]` | **No** en el plan gratuito. Sirve para decidir el personaje, no para el video |
| **Fish Audio Voice Design** | Voz nueva desde una descripción en unos 15 segundos | Generación gratis durante su lanzamiento; confirmar estado |

El orden importa: Speechma para saber en un minuto si el camino sirve, ElevenLabs para oír
el techo de calidad, Fish Audio como punto medio.

---

## 2. El motor de producción

Aquí está la tensión real del proyecto: **los motores más carismáticos no regalan el derecho
a monetizar, y los que lo regalan no eran expresivos.** Hasta ahora.

| Motor | Gratis | Expresividad | ¿Monetizable gratis? | Veredicto |
|---|---|---|---|---|
| **Qwen3-TTS** | Sí, siempre | Alta: control de emoción, diseño de voz y clonación | **Sí.** Licencia Apache 2.0 | **Elegido** |
| Gemini TTS | Sí, nivel gratuito | Alta: el tono se dirige por instrucción escrita | Sí, sin cláusula que lo prohíba | Alternativa en nube |
| Hume Octave 2 | Nivel gratuito limitado | La más alta del mercado en emoción: gana la mayoría de las comparaciones a ciegas | No en la práctica, es de pago | Descartado por la regla de gratuidad |
| ElevenLabs v3 | Plan gratuito | Muy alta | No, el plan gratuito excluye uso comercial | Solo para diseñar |
| Google Cloud TTS Chirp 3 HD | 1 millón de caracteres al mes | Media-alta, sin dirección por instrucción | Sí, dentro del límite | Respaldo |
| Azure Speech F0 | 500 000 caracteres | Alta | No: el derecho de uso está reservado al nivel de pago | Descartado |
| edge-tts | Sin límite práctico | Alta | No consta por escrito | Descartado |
| Piper | Sí | Baja | Según la voz | Ya probado: es el problema, no la solución |

### Por qué Qwen3-TTS

1. Es el único que cumple las tres condiciones a la vez: gratis para siempre, expresivo con
   control de emoción, y con licencia Apache 2.0, que permite publicar y monetizar sin pedir
   permiso a nadie.
2. Incluye **diseño de voz**, que es justo lo que este proyecto necesita.
3. Tiene el español entre sus idiomas, y está entrenado sobre más de cinco millones de horas
   de habla.

### Sobre el requisito de "nada local"

Ese requisito venía de una experiencia concreta: Piper suena mal. La conclusión correcta no
es que lo local suene mal, es que **Piper** suena mal. Qwen3-TTS también corre en el equipo
y está en otra categoría.

Si aun así se prefiere la nube, la opción es Gemini TTS, que ya se usa en la App 1 y dirige
el tono por instrucción escrita. Pierde el diseño de voz, pero gana en comodidad.

---

## 3. El catálogo de cuatro

Funciona mejor si cubre cuatro registros distintos, no cuatro variantes del mismo. Una voz
base que lleve el peso, una para ganchos y giros, una para comedia, y una para escenas
tristes. Dos personajes que suenen parecido gastan un puesto sin añadir nada.

---

## 4. Estado

- [x] Enfoque corregido: diseñar, no elegir
- [x] Herramientas de diseño gratuitas identificadas y verificadas
- [x] Motor de producción decidido: Qwen3-TTS, con Gemini TTS como alternativa
- [x] Diez personajes descritos
- [ ] Jhon los escucha y marca cuáles conectan
- [ ] Catálogo de cuatro cerrado

---

## Fuentes

- Páginas oficiales de Voice Design de ElevenLabs, Fish Audio y Speechma — funcionamiento,
  gratuidad y límites.
- Términos del plan gratuito de ElevenLabs — exclusión del uso comercial.
- Comparativas de modelos TTS de 2026 — Qwen3-TTS con licencia Apache, control de emoción y
  diseño de voz; Hume Octave 2 como referencia de expresividad.
- Documentación de Gemini-TTS — dirección del estilo por instrucción en lenguaje natural.
- Términos de producto de Microsoft — derechos de salida reservados al nivel de pago.
