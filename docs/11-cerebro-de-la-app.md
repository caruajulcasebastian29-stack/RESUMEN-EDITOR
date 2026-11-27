# 11 · El cerebro de la App 2

Sustituye a las partes del documento 10 que hacían el trabajo « a mano»: guion escrito por fuera,
cortes repartidos por tiempo y mapache pegado como imagen. Lo que sigue vigente del 10 es el
personaje, sus dos registros y las reglas de groserías.

## Qué tiene que hacer la app

1. **Aprender sola** de cada video de referencia que Jhon le dé: cortes, transiciones, música,
   cuándo y cómo aparece el personaje del canal, voz, narración y forma de enganchar.
   Lo aprendido se guarda en su memoria y se acumula video tras video.
2. **Entender** el resumen que entrega la App 1: qué película es, quién es quién, qué pasa en
   cada toma y en qué orden. La narración robótica de la App 1 solo sirve para entender;
   después se elimina.
3. **Detectar lo que falla** en ese resumen, comparándolo con lo aprendido.
4. **Rehacerlo**: narración nueva del mapache, audio nuevo, cortes ajustados a lo que se dice,
   transiciones, música y apariciones del personaje.
5. **Revisarse a sí misma** con medidas antes de mostrar nada a Jhon.

## Equipo de Jhon y qué cabe

ASUS TUF F15 · i7-12700H · RTX 3050 de 4 GB · 16 GB de RAM.

- Cabe un modelo de visión de unos 4B en la tarjeta. Uno de texto de 8-9B no cabe entero: se
  reparte entre tarjeta y RAM y va lento. Jhon aceptó «lento pero seguro», así que se usa el
  grande solo donde la calidad lo exige (escribir el guion) y el pequeño en lo repetitivo.
- La App 1 y la App 2 no deben correr a la vez (la RAM ya está casi llena con la App 1).
- Los modelos se cargan uno por uno, nunca dos al mismo tiempo.

## Herramientas elegidas (todas gratuitas)

| Tarea | Herramienta | Por qué esta |
|---|---|---|
| Detectar cortes y transiciones | **TransNetV2** (pytorch) + PySceneDetect de respaldo | TransNetV2 detecta también fundidos y transiciones graduales, que PySceneDetect pierde |
| Separar voz de música | **audio-separator** (modelos de UVR: MDX-Net / Roformer) | Mejor separación que Demucs solo; funciona en CPU |
| Transcribir con tiempos por palabra | **sherpa-onnx** con Whisper | Sin internet, sin cuenta; ya probado en el analizador |
| Quién habla (narrador o personaje de la película) | **sherpa-onnx diarización** (pyannote-segmentation + 3D-Speaker) | Funciona sin token de HuggingFace |
| Ver cada toma | **Ollama + qwen3-vl:4b** (alternativa gemma3:4b) | El mejor modelo de visión que cabe en 4 GB |
| Pensar y escribir | **Ollama + modelo de 8-9B** para guion; **4B** para tareas cortas | Salidas en JSON con esquema fijo, para que el resto del programa no se rompa |
| Memoria | **LanceDB** (base en archivos, sin servidor) + embeddings de Ollama | Búsqueda por parecido: «¿cómo engancharon en una de terror?» |
| Medir voz (tono, energía, ritmo) | librosa | Para comparar con las referencias, no a oído |
| Montaje | FFmpeg | Control exacto de cortes, transiciones y mezcla |
| Ventana | FastAPI + pywebview, empaquetado con PyInstaller | Ventana propia en Windows, sin consola |

## Cómo aprende de un video de referencia

Cada video pasa por estas capas y todo queda guardado en su ficha:

1. **Tomas:** inicio, fin, tipo de transición (corte seco, fundido, destello).
2. **Audio:** voz del narrador separada de la música; volumen de la música bajo la voz, silencios,
   efectos.
3. **Palabras:** transcripción con tiempo por palabra y quién habla.
4. **Imagen:** el modelo de visión describe cada toma y marca si es película, personaje del
   canal, tarjeta de texto, meme o autopromoción. Del personaje del canal se registra cuándo
   aparece, cuánto dura, en qué esquina y cuánto se mueve.
5. **Narración:** el modelo de texto marca el gancho, cada chiste (tipo y dónde cae), apodos,
   pausas, cambios de tono y el cierre. Se mide si los cortes caen en el final de las frases.
6. **Voz:** rango de tono, energía y velocidad, por frase.

Con todas las fichas, la app recalcula su **manual de estilo** (promedios y rangos) y guarda
ejemplos concretos en la memoria para consultarlos al escribir.

## Cómo trabaja con el resumen de la App 1

1. Lo analiza con las mismas capas.
2. Arma el **mapa de la historia**: personajes con nombre, hechos en orden y qué toma muestra cada
   hecho.
3. Hace un **diagnóstico**: tomas demasiado largas o repetidas, narración que no coincide con la
   imagen, gancho flojo, tramos sin ritmo.
4. Escribe la **narración nueva** por tramos, consultando la memoria. Cada frase lleva la toma
   donde va y su duración disponible; si no cabe, se reescribe.
5. Genera la voz (paso aparte, se decide al final) y **monta**: corta al ritmo de la voz, usa
   transiciones como las aprendidas, música con volumen que baja bajo la voz y el personaje solo
   donde corresponde.
6. **Autorrevisión** con medidas: ritmo de cortes, coincidencia imagen-narración, rango de tono
   de la voz, groserías por minuto. Lo que no pasa, se rehace antes de mostrarlo.

## Dónde se construye y se prueba

- El código vive en el repositorio. Las pruebas con modelos reales se corren en GitHub
  (servidores gratuitos) mediante un **banco de pruebas** automático que guarda sus resultados
  en la rama `resultados`.
- Jhon solo recibe el instalador cuando cada parte pasa sus pruebas.

## Orden de trabajo

1. Banco de pruebas en GitHub funcionando.
2. Aprendizaje de referencias (capas 1 a 6 + manual de estilo + memoria).
3. Entender y diagnosticar el resumen de la App 1.
4. Escribir la narración nueva.
5. Montaje (cortes, transiciones, música).
6. Voz (al final, por decisión de Jhon).
7. Personaje animado.
8. Ventana e instalador.
