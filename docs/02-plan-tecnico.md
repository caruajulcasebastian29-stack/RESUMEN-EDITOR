# Plan técnico de la App 2

Cómo construir lo que pide la especificación, qué conviene recortar y por qué. Donde se aparta
de la propuesta original, lo dice abiertamente.

> **Aviso de vigencia.** Las secciones 2, 5 y 8 de la primera versión de este documento quedaron
> desfasadas el 26 de noviembre, cuando las pruebas demostraron que varias suposiciones eran
> falsas. Están sustituidas por **[09 · Pipeline de análisis](09-pipeline-analisis.md)**, que es
> el procedimiento vigente. Aquí se conserva solo lo que sigue siendo cierto.

---

## 1. Lo primero que hay que arreglar: el contrato con la App 1

La especificación dice que la App 1 "entrega el video resumen narrado" y que la App 2
"rehace solo las partes con X". Esas dos frases no pueden cumplirse a la vez.

Si lo que llega es un MP4 terminado, para cambiar dos minutos de narración hay que regenerar
la voz y volver a renderizar todo, porque dentro del MP4 ya no existen el guion, los tiempos
ni los clips por separado: existe una sola imagen con un solo audio pegado.

**La App 1 no debe entregar solo un video, sino un proyecto.** Una carpeta con:

| Contenido | Para qué sirve |
|---|---|
| `guion.json` — frases, con tiempo de inicio y fin, y su escena | Reescribir una frase sin tocar las demás |
| `clips/` — los fragmentos de video ya recortados | Rearmar solo el tramo cambiado |
| `narracion/` — un archivo de audio por frase, no uno solo | Regenerar una frase y dejar el resto intacto |
| `proyecto.json` — qué clip va con qué frase y en qué orden | La receta para volver a armar el video |

Con eso, cambiar el lote 7 significa regenerar siete u ocho frases y volver a pegar dos
minutos, no veinte. La diferencia entre esperar un minuto y esperar media hora.

Encaja con algo que ya se pidió para la App 1: poder editar diálogos al final y regenerar solo
lo necesario. Es el mismo cambio, y conviene hacerlo una vez.

**Mientras la App 1 no exporte el proyecto, la App 2 no puede funcionar como se planteó.**
Es la primera tarea, antes de cualquier agente.

---

## 2. Qué se automatiza

**Sustituida.** La primera versión sostenía que el análisis visual costaba semanas y debía
hacerse a mano. Es falso, y quedó demostrado. Ver
**[09 · Pipeline de análisis](09-pipeline-analisis.md)**.

---

## 3. Cuántos videos y de qué canal

La especificación habla de treinta videos de dos canales. Dos correcciones, ambas en pie:

**Treinta son demasiados para empezar.** Entre cinco y ocho del mismo canal ya muestran el
patrón: duración de plano, densidad de información, cada cuánto entra un chiste. Del noveno en
adelante se repite. Treinta solo tiene sentido para afinar un manual que ya funcione.

**Mezclar dos canales promedia los dos estilos y no deja ninguno.** Si el manual sale de los
dos a la vez, el resultado no suena a ninguno: suena a promedio.

**Decidido:** se empieza con **@AsíPaso**. Del otro se tomará lo que falte más adelante.

---

## 4. Sobre las condiciones de YouTube

Aprender el estilo no es el problema. "Cortan cada dos segundos y medio", "meten un chiste cada
cuarenta segundos" son hechos sobre cómo se edita, y los hechos no son de nadie.

El problema era el paso de **descargar**. Y ese paso ya no hace falta para los videos de
referencia: Gemini acepta el enlace de YouTube directamente y lee el video sin que nada se
copie a ningún disco.

Para el análisis visual detallado, donde Claude mira los fotogramas, el archivo sí tiene que
estar accesible. Ahí la vía limpia son **los videos propios de la App 1**, que ya están en el
disco de Jhon y son suyos. Es además donde ese análisis más vale, porque sirve para comparar
su resultado contra las medidas del canal de referencia.

---

## 5. Los agentes

**Sustituida.** Bajaron de seis a tres, y de tres a dos. Ver
**[09 · Pipeline de análisis](09-pipeline-analisis.md)**.

---

## 6. La revisión por lotes

La parte más acertada de la propuesta y la más barata de construir. Marcar ✓ o ✗ es más rápido
que explicar con palabras lo que está mal, y evita la conversación que no se quiere tener.

1. El resumen se parte en lotes de dos minutos, cortando en cambio de escena, nunca a mitad de
   frase.
2. Cada lote se muestra con su video, su narración y su texto.
3. ✓ lo congela: no se vuelve a tocar.
4. ✗ lo marca para rehacer. El comentario es opcional.
5. Al rehacer, el guionista recibe la última frase del lote anterior y la primera del siguiente,
   para que el empalme no se note.
6. Vuelve solo ese lote.

### Los gustos se guardan en un archivo, no en un modelo

Cada ✗ con comentario es un ejemplo de lo que no gusta; cada ✓, de lo que sí. Se acumulan en un
archivo que el guionista lee antes de escribir:

```
PREFERENCIAS APRENDIDAS
- Rechazado: chistes que explican el chiste → cortar antes del remate
- Rechazado: "y es aquí donde todo cambia" → muletilla, prohibida
- Aprobado: preguntas directas al espectador en el gancho
```

Es lo más valioso del proyecto y lo más fácil de hacer. Después de treinta lotes revisados, ese
archivo describe el estilo propio de Jhon mejor que el manual sacado de otros canales. Y no hay
que reentrenar nada: es un archivo que crece.

---

## 7. Lo que sí y lo que no se puede prometer

**Se transfiere bien** —son medidas, y una medida se copia: duración de plano, cortes por
minuto, palabras por minuto, dónde va el gancho, cuánta información por minuto, cada cuánto
entra un chiste, cuándo callar, cómo cerrar.

**Se transfiere a medias:** el vocabulario y el tipo de frase. El modelo imita el registro con
bastante fidelidad si el manual tiene ejemplos suficientes.

**No se transfiere:** que el chiste dé risa, y que la voz lo diga en el momento exacto. Eso no
es una regla que se extraiga de un video, es talento de quien escribe y de quien narra.

Por eso el circuito de ✓ y ✗ importa más que el análisis de los treinta videos: el análisis da
la estructura, la revisión da la gracia.

---

## 8. Herramientas

**Sustituida.** Ver **[09 · Pipeline de análisis](09-pipeline-analisis.md)**.

---

## 9. Orden de trabajo

| # | Paso | Estado |
|---|---|---|
| 0 | La App 1 exporta el proyecto, no solo el MP4 | **Pendiente. Bloquea la revisión por lotes** |
| 1 | Elegir las 4 voces | Aplazado por decisión de Jhon |
| 2 | Validar que el análisis da detalle real, no resumen | **Hecho.** 60 entradas de 60, ver [07](07-resultado-prueba.md) |
| 3 | Elegir canal base | **Hecho.** @AsíPaso |
| 4 | Primer borrador del manual de estilo | **Hecho**, con lo verificado separado de lo supuesto, ver [08](08-manual-estilo-asipaso.md) |
| 5 | Montar las herramientas de análisis | **Hecho.** letmewatch verificado; Local Whisper pendiente de conectar |
| 6 | Analizar un video entero con el pipeline de [09](09-pipeline-analisis.md) | Pendiente: falta el archivo en una carpeta conectada |
| 7 | Reeditar 2 minutos de un resumen propio | Pendiente |
| 8 | Decidir si convence | Pendiente |
| 9 | Construir la aplicación completa | Pendiente |

Los pasos 6 y 7 son la prueba que decide el proyecto. Hasta tenerla, no conviene escribir la
aplicación entera: si los dos minutos no se parecen a lo que se busca, lo que hay que cambiar
es el enfoque, no la interfaz.
