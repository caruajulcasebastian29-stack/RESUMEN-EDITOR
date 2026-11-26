# Resultado de la prueba manual

**Video:** «El espanta tiburones» (Shark Tale), @AsíPaso, 22:22 de duración.
**Bloque analizado:** 00:00 a 00:59.
**Configuración:** Gemini 4 Hydrogen, pensamiento en Bajo, salida estructurada con esquema
obligatorio, recorte 0s–1m0s, 1 fps, comprensión agencial desactivada. Entrada: 6 331 fichas.

## Veredicto

**El método funciona.** Devolvió 60 entradas, de la 0 a la 59, sin omitir ningún segundo y sin
resumir. El esquema obligatorio era la pieza que faltaba: con él, la respuesta en prosa deja de
ser una opción para el modelo.

Queda confirmado el tamaño de bloque en **60 segundos**. No hace falta bajarlo a 30.

## Medidas obtenidas de este minuto

| Medida | Valor | Nota |
|---|---|---|
| Cortes | 33 en 60 s | Un plano cada 1,8 s de media |
| Transiciones | 0 | Todo corte seco: ni un fundido en el minuto |
| Ritmo de narración | ~204 palabras por minuto | Muy rápido, por encima de lo habitual |
| Silencios | 2 segundos sin voz | Narración prácticamente continua |
| Rótulos de personaje | 4 | LENNY, FRANKIE, KATIE CURRENT, MUSSEL CROWE |

Pendiente de confirmar con más bloques, pero ya es material utilizable para el manual.

## Calidad por campo

| Campo | Veredicto | Comentario |
|---|---|---|
| `pantalla` | **Excelente** | Concreto y específico, no genérico. Describe acciones reales, no «escena de la película» |
| `narracion` | **Excelente** | Transcripción literal partida por segundos. Leídas seguidas reconstruyen el texto completo |
| `corte` | **Bueno** | Coherente con lo que se describe. Da la medida más importante del montaje |
| `plano` | **Bueno** | Relleno de forma consistente |
| `texto_en_pantalla` | **Bueno** | Detectó la marca de agua fija y los rótulos de personaje |
| `meme_o_sticker` | **Sin confirmar** | Solo detectó un elemento de redes sociales desde el s32. Falta verificar contra el video |
| `sonido` | **Falla** | Demasiado grueso: «música de fondo» en casi todo el minuto |
| `energia_voz` | **Falla** | No está oyendo, está deduciendo por contexto: 3 por defecto, 4 cuando sale el narrador, 1 cuando no hay voz |

## Correcciones que salen de la prueba

1. **El audio se mide, no se pregunta.** `sonido` y `energia_voz` salen del propio archivo de
   audio —volumen, velocidad de habla, tono, silencios— con una pasada aparte. Es barato,
   objetivo y da un número por segundo. Pedírselo al modelo fue un error de diseño.
2. **Añadir un campo de rótulo de personaje.** El canal nombra a cada personaje la primera vez
   que aparece. Es una regla de estilo copiable que no estaba en la lista original.
3. **Mantener el bloque en 60 segundos.** Confirmado por la prueba.

## Hallazgo de estilo

@AsíPaso **no usa gancho**. Abre con el nombre del canal y el título, y pasa directo a contar
la historia en orden cronológico: «Así pasó, el espanta tiburones. La historia comienza en las
profundidades del océano…».

Esto contradice el guion marcado que se preparó antes, que abría con una escena de tensión
antes del título. Son dos estrategias distintas de retención y hay que elegir una.

Además, el narrador aparece en cámara en su estudio, intercalado con las imágenes de la
película (segundos 0, 15 a 17 y 59). Es una decisión de formato, no solo de edición.

**Decisión pendiente de Jhon:** copiar el arranque de @AsíPaso o conservar el gancho.

## Estado

- [x] Método validado: 60 entradas completas, sin resumir
- [x] Tamaño de bloque confirmado en 60 s
- [ ] Confirmar si hay memes reales en el primer minuto
- [ ] Decidir el estilo de arranque
- [ ] Programar la pasada automática de los 23 bloques
