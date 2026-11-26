# Voces

Requisitos de la especificación: no locales, expresivas, gratuitas, con derecho a usarlas en
el canal, y un catálogo final de máximo cuatro.

El requisito que elimina más opciones no es la calidad: es el derecho de uso. Muchos
servicios regalan voces excelentes y prohíben publicarlas en un canal monetizado.

---

## 1. Comparación de motores

| Motor | Gratis al mes | Expresividad en español | ¿Se puede monetizar? | Veredicto |
|---|---|---|---|---|
| **Gemini TTS** (AI Studio / API) | Sin cargo en el nivel gratuito | **Alta.** El tono se dirige escribiendo una instrucción: "bájale la voz como si contaras un secreto" | Sí. No hay cláusula que lo prohíba, y Google no reclama propiedad sobre lo generado | **Elegido** |
| Google Cloud TTS — Chirp 3 HD | 1 millón de caracteres | Media-alta, pero sin dirección por instrucción | Sí, dentro del límite | Respaldo |
| Google Cloud TTS — WaveNet | 4 millones de caracteres | Media | Sí, dentro del límite | Respaldo barato |
| Azure Speech, nivel F0 | 500 000 caracteres | Alta, con estilos por etiqueta | **No.** El derecho de uso de la salida está reservado al nivel de pago; el gratuito es para evaluar | Descartado |
| edge-tts (voces de Edge) | Sin límite práctico | Alta. Dalia y Jorge son el estándar de hecho en canales en español | **No con certeza.** Microsoft no publica ningún documento que conceda redistribución comercial | Solo para comparar |
| ElevenLabs, plan gratuito | ~10 000 caracteres | Muy alta | **No.** El plan gratuito excluye uso comercial | Descartado |
| Kokoro-82M | Ilimitado | Media | Sí, licencia Apache 2.0 | Descartado: es local |
| Coqui XTTS v2 | Ilimitado | Alta, con clonación | **No.** La licencia excluye el uso comercial | Descartado |
| Piper | Ilimitado | Baja | Según la voz | Ya probado: poco expresivo |

### Por qué Gemini TTS

1. **Es el único que resuelve el requisito del "tono de voz según la escena".** En los demás
   motores se elige una voz y se acepta como suene. En Gemini el tono se escribe: la misma
   voz narra un giro de guion con suspenso y una escena triste con la voz baja, porque se le
   indica con una frase. La especificación pide exactamente eso.
2. **Ya se usa en la App 1.** Una sola cuenta, una sola clave, un solo sitio donde fallar.
3. **No es local**, que era el requisito explícito.
4. **El límite por petición encaja con los lotes de 2 minutos.** Cada petición admite unos
   8 000 tokens de entrada y hasta cerca de once minutos de audio: un lote de dos minutos
   entra entero y sobra margen. La arquitectura de lotes y el límite del motor coinciden sin
   forzar nada.
5. **Admite marcas dentro del texto** del tipo `[susurra]`, `[con emoción]`, `[muy lento]`,
   que el Guionista puede dejar escritas en el guion para que la voz las obedezca.

### Nota sobre las voces de Edge

Dalia y Jorge son, con diferencia, las mejores voces gratuitas de español latino, y están en
casi todos los canales de resúmenes. Tentador, pero el derecho de uso no está concedido por
escrito y el canal va a estar monetizado. Sirven para comparar y para calibrar el oído,
nunca para el video final.

---

## 2. Las 10 candidatas

Cada una es una **voz más una instrucción de actuación**, no una voz suelta. La instrucción
es la mitad del resultado.

Se escuchan en la cabina de voces y se marcan con check o X. De las aprobadas salen las
cuatro del catálogo.

| # | Papel | Voz | Para qué escena |
|---|---|---|---|
| 01 | Intriga fría | Charon | Aperturas y ganchos |
| 02 | Energía TikTok | Puck | Vertical, primeros segundos |
| 03 | Cómico seco | Zubenelgenubi | Comedias, escenas absurdas |
| 04 | Cine grave | Algenib | Thriller, terror, tráiler |
| 05 | Cercana cálida | Sulafat | Drama, romance, animación |
| 06 | Confidente | Enceladus | Giros y avisos al espectador |
| 07 | Acelerado informativo | Iapetus | Tramos de contexto y datos |
| 08 | Dramático contenido | Achernar | Escenas tristes y finales |
| 09 | Amigo exagerado | Fenrir | Narrador que reacciona |
| 10 | Neutro latino | Orus | Voz base del canal |

Las instrucciones completas de cada una están en la cabina de voces, con botón para copiarlas.

---

## 3. Qué cuatro conviene elegir

Una recomendación para cuando llegue el momento de decidir, sujeta a lo que Jhon escuche.

Un catálogo de cuatro funciona mejor si cubre cuatro registros distintos, no cuatro variantes
del mismo:

| Puesto | Función | Candidata natural |
|---|---|---|
| 1 | Voz base del canal, la que más se usa | 10 — Neutro latino |
| 2 | Para ganchos y giros | 01 — Intriga fría, o 06 — Confidente |
| 3 | Para comedia | 03 — Cómico seco, o 09 — Amigo exagerado |
| 4 | Para escenas tristes y finales | 08 — Dramático contenido |

Dos voces muy parecidas gastan un puesto del catálogo sin añadir nada: si dos aprobadas
suenan casi igual, conviene quedarse con una y usar el puesto libre para un registro que
falte.

---

## 4. Estado

- [x] Motores comparados y derechos verificados
- [x] Diez candidatas preparadas con su instrucción
- [ ] Jhon las escucha y marca check o X
- [ ] Catálogo de cuatro cerrado

---

## Fuentes

- Documentación de Gemini-TTS, Google Cloud — dirección del estilo por instrucción en
  lenguaje natural y límites por petición.
- Página de precios de la API de Gemini — nivel gratuito.
- Términos de producto de Microsoft — derechos de uso de la salida de voces neuronales
  reservados al nivel de pago.
- Microsoft Q&A — ausencia de documentación que conceda uso comercial a edge-tts.
- Página de precios de Google Cloud Text-to-Speech — asignaciones mensuales gratuitas.
