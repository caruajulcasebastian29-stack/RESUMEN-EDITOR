# Cómo se analiza un video de referencia

Este documento sustituye a las secciones 2, 5 y 8 del plan técnico, que quedaron desfasadas
el 26 de noviembre. Es el procedimiento vigente.

## Qué cambió y por qué

| Lo que decía el plan | Lo que sabemos ahora |
|---|---|
| El análisis visual automático cuesta semanas, mejor a mano | Falso. Se automatiza: Gemini lee el video desde el enlace, y Claude puede mirar los fotogramas directamente |
| Hay que descargar los videos de referencia | Falso. Gemini acepta el enlace de YouTube sin descargar nada |
| Los memes son adornos sobre la película | Falso. Son **clips a pantalla completa** que cortan el resumen durante 3 a 5 segundos y luego vuelven |
| La transcripción con faster-whisper | Corre en el equipo de Jhon con Local Whisper, no en el entorno de Claude |
| El tono de voz lo evalúa el modelo | Falso. Lo inventa. Se mide sobre la onda de audio |

## El reparto actual

| Capa | Quién lo hace | Fiabilidad |
|---|---|---|
| **Imagen**: qué se ve, clips de reacción, textos en pantalla | Claude mira los fotogramas con letmewatch | Observado |
| **Cortes**: segundo exacto, duración de plano, transiciones | Detección de escena sobre el video | Medido |
| **Habla**: transcripción literal con tiempos | Local Whisper, en el equipo de Jhon | Medido |
| **Audio**: volumen, silencios, ritmo | Análisis de la señal | Medido |
| **Reglas de escritura**: humor, conectores, arcos de tono | Claude, leyendo la transcripción | Razonado sobre texto real |

Ninguna capa depende de que un modelo adivine lo que no puede percibir. Esa fue la lección
del campo `energia_voz`, que vino relleno sin haber oído nada.

## Procedimiento por video

### Paso 1 — Estructura del conjunto

Una sola pasada sobre el video completo para obtener el mapa: dónde acaba el gancho, dónde
está el giro, qué se cuenta y qué se salta, cómo cierra. Aquí un resumen es lo correcto,
porque lo que se pide es la forma del conjunto.

### Paso 2 — Transcripción

Local Whisper devuelve el texto con marcas de tiempo. De aquí salen el conteo de palabras por
minuto, los conectores, las muletillas y el material para las reglas de humor.

### Paso 3 — Cortes

Detección de cambio de escena sobre el archivo. Devuelve la lista de cortes con su segundo y
la duración real de cada plano. Es la medida que más pesa para copiar el ritmo de montaje.

### Paso 4 — Fotogramas

Un fotograma por plano, con su marca de tiempo. Claude los mira en tandas y anota:

- Qué se ve y de dónde viene la imagen: la película, el narrador, un gráfico, o una
  **inserción externa**.
- Si es inserción externa: qué muestra, cuánto dura y a qué reacciona.
- Textos en pantalla y rótulos de personaje.

### Paso 5 — Audio como señal

Volumen por segundo, silencios y su duración, velocidad de habla. Sin modelos de por medio.

### Paso 6 — Ficha del video

Las cinco capas se funden en una ficha. Lo observado y lo medido se marcan como tales;
nada entra como supuesto.

## Los clips de reacción

Funcionan así: el resumen va narrando, ocurre algo, **todo se corta**, aparece un clip a
pantalla completa de 3 a 5 segundos con su propio audio, y al terminar el resumen continúa
como si nada.

Por eso son fáciles de detectar en los fotogramas: la imagen cambia por completo a algo que
no pertenece a la película.

Lo que hay que aprender no es qué clip usaron, sino **qué lo dispara**. La regla es del tipo
«cuando el protagonista hace una estupidez, entra una reacción de 3 a 5 segundos y el narrador
calla». El clip concreto es una pieza intercambiable de la biblioteca.

## Los agentes, otra vez a la baja

El plan ya había bajado de seis agentes a tres. Con el reparto de arriba, el Analista deja de
ser un agente: es un procedimiento de medición más Claude mirando. Quedan dos:

| Papel | Qué hace | Con qué |
|---|---|---|
| **Guionista** | Reescribe el guion lote por lote con el manual y las preferencias aprendidas | Gemini, nivel gratuito |
| **Revisor** | Comprueba el empalme con el lote anterior y el siguiente, repeticiones de chistes, humor fuera de lugar | Ollama, local |

## Herramientas

| Función | Herramienta | Dónde corre |
|---|---|---|
| Fotogramas y detección de escena | letmewatch, ffmpeg | Entorno de Claude |
| Transcripción | Local Whisper | Equipo de Jhon |
| Medición de audio | numpy y scipy | Entorno de Claude |
| Lectura del video completo por enlace | Gemini, nivel gratuito | Nube |
| Reescritura del guion | Gemini, nivel gratuito | Nube |
| Continuidad entre lotes | Ollama | Equipo de Jhon |
| Montaje final | ffmpeg | Equipo de Jhon |

Todo gratuito, según la regla del proyecto.

## Lo que todavía no cubre nada

Reconocer sonidos que no son voz: una carcajada enlatada, un disco rayado, un golpe de efecto.
Whisper transcribe habla. La medición de la onda detecta que hay un pico, no qué lo produce.

En la práctica se resuelve solo, porque esos sonidos acompañan a un clip de reacción y el clip
sí se ve en la imagen. Queda anotado por si algún día deja de bastar.
