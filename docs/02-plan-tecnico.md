# Plan técnico de la App 2

Este documento explica cómo construir lo que pide la especificación, qué partes conviene
recortar y por qué. Donde se aparta de la propuesta original, lo dice abiertamente.

---

## 1. Lo primero que hay que arreglar: el contrato con la App 1

La especificación dice que la App 1 "entrega el video resumen narrado" y que la App 2
"rehace solo las partes con X". Esas dos frases no pueden cumplirse a la vez.

Si lo que llega es un archivo MP4 terminado, para cambiar dos minutos de narración hay que
volver a generar la voz y volver a renderizar todo, porque dentro del MP4 ya no existen el
guion, los tiempos ni los clips por separado: existe una sola imagen con un solo audio pegado.

**Entonces la App 1 no debe entregar solo un video, sino un proyecto.** Una carpeta con:

| Contenido | Para qué sirve |
|---|---|
| `guion.json` — frases, con tiempo de inicio y fin, y la escena a la que pertenecen | Permite reescribir una frase sin tocar las demás |
| `clips/` — los fragmentos de video ya recortados | Permite rearmar solo el tramo cambiado |
| `narracion/` — un archivo de audio por frase, no uno solo | Permite regenerar una frase y dejar el resto intacto |
| `proyecto.json` — qué clip va con qué frase y en qué orden | Es la receta para volver a armar el video |

Con eso, cambiar el lote 7 significa regenerar siete u ocho frases y volver a pegar dos
minutos de video, no veinte. Es la diferencia entre esperar un minuto y esperar media hora.

Esto encaja con algo que ya se pidió para la App 1: poder editar partes del diálogo al final
y regenerar solo los pasos necesarios. Es el mismo cambio, y conviene hacerlo una sola vez.

**Mientras la App 1 no exporte el proyecto, la App 2 no puede funcionar como se planteó.**
Es la primera tarea, antes de cualquier agente.

---

## 2. Qué se automatiza y qué no

La propuesta pide analizar once dimensiones de cada video. No todas cuestan lo mismo ni
valen lo mismo, y tratarlas por igual es lo que haría que este proyecto no termine nunca.

### Se automatiza (barato y útil)

| Dimensión | Cómo | Coste real |
|---|---|---|
| Narración completa con tiempos | Transcripción automática del audio | Minutos por video |
| Tono, energía, pausas | Se mide del propio audio: volumen, velocidad de habla, duración de silencios | Automático |
| Cortes y duración de plano | Detección de cambio de escena sobre el video | Automático |
| Ritmo | Se calcula: palabras por minuto, cortes por minuto, silencios por minuto | Automático |
| Estructura de la trama | El modelo lee la transcripción y marca gancho, desarrollo, giro y cierre | Una consulta por video |
| Chistes | El modelo los localiza en la transcripción y los clasifica | Una consulta por video |

Estas seis cubren el guion, la narración y el ritmo: es decir, casi todo lo que decide si un
resumen aburre o no.

### Se hace a mano al principio (caro y de poco retorno)

Transiciones, acercamientos, imágenes congeladas, textos en pantalla, memes y stickers.

Detectar eso automáticamente obliga a pasar un modelo de visión por miles de fotogramas de
cada video: semanas de trabajo, lento y propenso a errores. Y el resultado final cabe en
media página: "un meme cada cuarenta segundos, de dos segundos, abajo a la derecha".

Ese mismo dato se obtiene viendo cinco videos con un cronómetro y llenando un formulario,
en una tarde. **Se empieza así.** Si más adelante hace falta precisión, se automatiza
entonces, con el proyecto ya funcionando.

---

## 3. Cuántos videos y de qué canal

La especificación habla de treinta videos de dos canales. Dos correcciones:

**Treinta son demasiados para empezar.** Entre cinco y ocho videos del mismo canal ya
muestran el patrón: la duración de plano, la densidad de información, cada cuánto entra un
chiste. Del noveno en adelante se repite lo mismo. Treinta videos solo tienen sentido para
afinar, cuando ya exista un manual que funcione.

**Mezclar dos canales desde el principio promedia los dos estilos y no deja ninguno.**
@enminutos y @AsíPaso no narran igual; si el manual sale de los dos a la vez, el resultado
no suena a ninguno de los dos, suena a promedio. Conviene elegir uno como base, lograr que
el canal funcione con ese estilo, y después tomar del otro lo que falte.

**Decisión pendiente de Jhon: con cuál de los dos canales se empieza.**

---

## 4. Sobre las condiciones de YouTube

La especificación ya señala que hay que revisar esto, y conviene ser claro.

Aprender el estilo no es el problema. "Cortan cada dos segundos y medio", "meten un chiste
cada cuarenta segundos", "abren con una pregunta" son hechos sobre cómo se edita, y los
hechos no son propiedad de nadie. Un manual de estilo con esas medidas es legítimo, y el
plan de guardar solo el conocimiento y borrar las copias es el enfoque correcto.

El problema es el paso de **descargar** los videos. Las condiciones de servicio de YouTube
no permiten descargar contenido fuera de las funciones que la propia plataforma ofrece, y
eso no cambia según para qué se vaya a usar el archivo.

Rutas más seguras, en orden:

1. **Analizar viendo.** Los datos visuales se llenan a mano, como ya se dijo arriba. Para la
   narración, los subtítulos que YouTube muestra públicamente se pueden leer sin descargar
   el video.
2. **Usar material propio.** Los resúmenes que la App 1 ya generó sirven para medir el
   contraste: qué tiene el canal de referencia que el propio no tiene.
3. **Pedir permiso.** Son dos canales; un mensaje preguntando si permiten un análisis de
   estilo es gratis y resuelve el asunto de raíz.

Lo que no conviene es montar la descarga dentro de la aplicación y que quede como una
función permanente del producto.

---

## 5. Los agentes: de seis a tres

Seis agentes suenan ordenados, pero cada paso intermedio es un sitio donde el resultado se
degrada: el Editor no sabe por qué el Guionista puso una pausa, el de Memes no sabe de qué
se ríe el chiste. Y los modelos locales de Ollama que caben en un equipo normal (7 u 8 mil
millones de parámetros) no escriben comedia en español lo bastante bien como para que
dividir el trabajo en seis partes mejore nada.

Tres papeles bastan:

| Papel | Qué hace | Con qué |
|---|---|---|
| **Analista** | Lee los videos de referencia y produce las fichas y el manual. Se ejecuta una vez, no en cada video. | Transcripción + modelo de lenguaje |
| **Guionista** | Reescribe el guion lote por lote aplicando el manual y los gustos aprendidos. Decide también dónde va un meme y dónde una pausa, porque eso es parte de escribir el chiste. | Gemini (nivel gratuito) |
| **Revisor** | Comprueba que el lote reescrito encaje con el anterior y el siguiente, que no se repitan chistes y que no haya humor en escenas tristes. | Ollama, local, es suficiente |

El montaje —cortar, pegar, poner el meme en pantalla, mezclar el audio— no necesita un
agente. Es un programa que ejecuta las instrucciones que dejó el Guionista. Un modelo de
lenguaje ahí solo añade errores.

---

## 6. La revisión por lotes

Esta parte de la propuesta es la más acertada y la más barata de construir. Marcar check o X
es más rápido que explicar con palabras lo que está mal, y evita la conversación que no se
quiere tener.

Cómo funciona por dentro:

1. El resumen se parte en lotes de dos minutos, cortando en cambio de escena, nunca a mitad
   de frase.
2. Cada lote se muestra con su video, su narración y su texto.
3. Check lo congela: ese lote no se vuelve a tocar.
4. X lo marca para rehacer. El comentario es opcional.
5. Al rehacer un lote, el Guionista recibe también la última frase del lote anterior y la
   primera del siguiente, para que el empalme no se note.
6. Vuelve solo ese lote. Los demás siguen con check.

### Los gustos se guardan en un archivo, no en un modelo

Cada X con comentario es un ejemplo de lo que no gusta. Cada check, de lo que sí. Eso se
acumula en un archivo de texto que el Guionista lee al principio de cada trabajo:

```
PREFERENCIAS APRENDIDAS
- Rechazado: chistes que explican el chiste → cortar antes del remate
- Rechazado: "y es aquí donde todo cambia" → muletilla, prohibida
- Aprobado: preguntas directas al espectador en el gancho
- Aprobado: cortar la frase y retomarla después del clip
```

Esto es lo más valioso de todo el proyecto y lo más fácil de hacer. Después de treinta lotes
revisados, ese archivo describe el estilo propio de Jhon mejor que el manual sacado de otros
canales. Y no hay que reentrenar nada: es un archivo que crece.

---

## 7. Lo que sí y lo que no se puede prometer

La especificación pide "el mismo estilo y calidad que los videos estudiados" y añade que el
parecido exacto no está garantizado. Esa reserva es correcta, y conviene precisarla, porque
marca dónde conviene gastar el esfuerzo.

**Se transfiere bien** —son medidas, y una medida se copia:
duración de plano, cortes por minuto, palabras por minuto, dónde va el gancho, cuánta
información por minuto, cada cuánto entra un chiste, cuándo callar, cómo cerrar.
Esto es la mitad de la sensación de "está bien editado", y es alcanzable.

**Se transfiere a medias:** el vocabulario y el tipo de frase. El modelo imita el registro
con bastante fidelidad si el manual tiene ejemplos suficientes.

**No se transfiere:** que el chiste dé risa, y que la voz lo diga en el momento exacto. Eso
no es una regla que se extraiga de un video, es talento de quien escribe y de quien narra.
Un manual puede decir "aquí va un chiste de dos segundos sobre lo absurdo de la escena";
que ese chiste sea bueno depende del modelo que lo escriba y del criterio de Jhon al marcar
la X.

Por eso el circuito de check y X importa más que el análisis de los treinta videos: el
análisis da la estructura, la revisión da la gracia.

---

## 8. Herramientas

Todas gratuitas, según la regla del proyecto.

| Función | Herramienta | Nota |
|---|---|---|
| Transcripción con tiempos | faster-whisper | Local, gratis, buena en español |
| Detección de cortes | ffmpeg | Ya se usa en la App 1 |
| Medición de audio | librosa | Volumen, velocidad, silencios |
| Guion y análisis | Gemini, nivel gratuito | Ya se usa en la App 1 |
| Revisión y continuidad | Ollama, local | Tarea sencilla, modelo pequeño basta |
| Narración | Gemini TTS | Ver `03-voces.md` |
| Montaje | ffmpeg | Sin modelos de por medio |
| Ventana de la aplicación | La misma base que la App 1 | Un solo instalador a mantener |

---

## 9. Orden de trabajo

Sigue el orden que planteó Jhon, con la corrección del punto 1 delante.

| # | Paso | Resultado comprobable |
|---|---|---|
| 0 | La App 1 exporta el proyecto, no solo el MP4 | Una carpeta con guion, clips y audio por frase |
| 1 | Elegir las 4 voces | `03-voces.md` cerrado, con las 4 decididas |
| 2 | Analizar un video y revisar su ficha | Una ficha completa que Jhon valide |
| 3 | Escribir el manual de estilo con ese video | Media página de reglas medibles |
| 4 | Reeditar 2 minutos de un resumen propio | Un video de 2 minutos comparable con la referencia |
| 5 | Decidir si convence | Sigue adelante, o se ajusta el enfoque |
| 6 | Construir la aplicación completa | Instalador con revisión por lotes |
| 7 | Completar hasta 8 videos del canal base | Manual afinado |

Los pasos 2 a 4 son la prueba que decide el proyecto. Hasta tenerla, no conviene escribir
la aplicación entera: si los dos minutos no se parecen a lo que se busca, lo que hay que
cambiar es el enfoque, no la interfaz.
