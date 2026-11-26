# Plantillas de análisis

Dos formatos: la ficha que se llena por cada video de referencia, y el manual de estilo que
sale de comparar las fichas.

El objetivo de ambos es que todo quede en **números y reglas comprobables**. "Narración
dinámica" no sirve para nada; "150 palabras por minuto y ningún silencio de más de medio
segundo" sí, porque se puede medir en el video propio y ver si cumple.

---

## 1. Ficha por video

Las casillas marcadas como automáticas las llena la aplicación. Las demás se llenan a mano
viendo el video, al menos al principio.

```
FICHA DE VIDEO
Canal:
Duración total:
Película resumida:
Fecha de análisis:

-- GANCHO (automático + revisión) ------------------
Duración del gancho hasta la primera imagen de la película:
Texto literal de la primera frase:
Tipo de apertura:  pregunta / afirmación extrema / escena sin contexto / dato
Segundo en que aparece el título de la película:
¿Adelanta el final?:  sí / no

-- NARRACIÓN (automático) --------------------------
Palabras por minuto:
Longitud media de frase, en palabras:
Silencio más largo, en segundos:
Silencios por minuto:
Palabras y muletillas repetidas:

-- TONO (automático) -------------------------------
Rango de volumen:  parejo / con picos
Dónde sube la energía, en segundos:
Dónde baja, en segundos:
Cambios de velocidad notables:

-- CORTES (automático) -----------------------------
Cortes por minuto:
Duración media de plano, en segundos:
Plano más largo:
Plano más corto:

-- TRAMA (una consulta al modelo) ------------------
Qué se cuenta y qué se salta:
Dónde está el giro, en segundos:
Cómo cierra:  final completo / final oculto / gancho a otro video

-- CHISTES (una consulta al modelo) ----------------
Cantidad total:
Cada cuántos segundos, en promedio:
Tipos:  exageración / comparación absurda / comentario al personaje / ruptura
Escenas sin ningún chiste:

-- VISUAL (a mano) ---------------------------------
Transiciones usadas y cuántas veces:
Acercamientos por minuto:
Imágenes congeladas:  cuántas y de qué duración
Textos en pantalla:  cuántos, dónde, cuánto duran
Subtítulos:  sí / no — estilo

-- MEMES Y STICKERS (a mano) -----------------------
Cantidad total:
Cada cuántos segundos:
Duración media:
Posición habitual en pantalla:
Qué tipo:

-- SONIDO (a mano) ---------------------------------
Hay música de fondo:  siempre / por tramos / no
Volumen de la música respecto de la voz:
Efectos de sonido:  cuántos y de qué tipo
Silencios totales usados a propósito:

-- CONCLUSIÓN (una línea) --------------------------
Qué hace este video que lo hace funcionar:
```

---

## 2. Manual de estilo

Sale de comparar las fichas. Es el documento que el Guionista lee antes de escribir, así que
tiene que ser corto y ejecutable: reglas, no descripciones.

```
MANUAL DE ESTILO
Canal base:
Videos analizados:
Última actualización:

-- REGLAS DE APERTURA ------------------------------
El gancho dura como máximo ___ segundos.
Abre con: ___
El título de la película se dice en el segundo ___.
Prohibido en el gancho: ___

-- REGLAS DE NARRACIÓN -----------------------------
Ritmo objetivo: ___ palabras por minuto.
Frases de ___ palabras como máximo.
Ningún silencio de más de ___ segundos, salvo ___
Enlaces entre escenas permitidos: ___
Muletillas prohibidas: ___

-- REGLAS DE HUMOR ---------------------------------
Un chiste cada ___ segundos como máximo.
Tipos que funcionan: ___
Sin humor en: ___
Longitud máxima del chiste: ___ segundos.

-- REGLAS DE MONTAJE -------------------------------
Duración de plano: entre ___ y ___ segundos.
Transiciones permitidas: ___
Un meme cada ___ segundos, de ___ segundos, en ___
Textos en pantalla: ___

-- REGLAS DE SONIDO --------------------------------
Música: ___
Volumen de la música respecto de la voz: ___
Efectos: ___

-- REGLAS DE CIERRE --------------------------------
Termina con: ___
Duración del cierre: ___ segundos.
```

---

## 3. Preferencias aprendidas

Este archivo no se escribe a mano: lo llena la propia aplicación cada vez que Jhon marca
un lote con check o con X. Es el que más peso tiene de los tres, porque describe su criterio
y no el de otro canal.

```
PREFERENCIAS APRENDIDAS
Lotes revisados: ___

RECHAZADO
- (motivo) -> (regla que se deduce)

APROBADO
- (qué se hizo) -> (regla que se deduce)

REGLAS FIRMES
(las que se han repetido tres veces o más)
```

Cuando una regla aparece tres veces, pasa a firmes y el Guionista la trata como obligatoria.
