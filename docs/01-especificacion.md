# Especificación de la App 2

Este documento recoge el proyecto tal como lo planteó Jhon. No añade decisiones técnicas:
esas van en el plan técnico.

## 1. La idea

Un canal sostenido por dos aplicaciones:

- **App 1 — Resumen Labs.** Hace el trabajo pesado y entrega el video resumen narrado.
- **App 2 — El editor.** Recibe un resumen ya hecho y lo edita con el estilo aprendido
  para que no sea aburrido. Usa Ollama y agentes.

Todos los agentes y herramientas deben ser gratuitos.

## 2. Entrenamiento con videos

La aplicación se entrena con unos 30 resúmenes de **@enminutos** y **@AsíPaso**, estudiando
cada video de principio a fin.

| Qué estudiar | Qué debe aprender |
|---|---|
| Introducción y gancho | Cómo empiezan y atrapan en los primeros segundos |
| Trama | Qué cuentan, destacan o saltan, cómo crean intriga y cómo cierran |
| Narración | Vocabulario, forma de hablar, tipo de frases y enlaces entre escenas |
| Tono de voz | Emoción, energía, velocidad, pausas y cambios según la escena |
| Cortes | Dónde cortan, cuánto dura cada plano y cómo coincide la imagen con la voz |
| Transiciones | Cuáles usan, cuándo y cuánto duran |
| Edición visual | Acercamientos, velocidad, imágenes congeladas, textos y subtítulos |
| Memes y stickers | Cuáles, cuántos, cuándo, dónde y por cuánto tiempo |
| Chistes | Cómo se construyen, cada cuánto aparecen y cuándo no ponerlos |
| Sonido | Música, efectos, silencios y volumen respecto de la voz |
| Ritmo | Cómo se combina todo para que no aburra |

### Forma de hacerlo (propuesta por probar)

1. Se agregan los videos uno por uno.
2. La aplicación convierte la narración en texto, con los tiempos.
3. Detecta cortes, transiciones, pausas, música y efectos.
4. Revisa las imágenes para reconocer acercamientos, textos, memes y stickers.
5. Crea una **ficha por video**, indicando en qué segundo ocurre cada cosa.
6. Compara las fichas y forma un **manual de estilo y edición**.
7. Borra las copias temporales y conserva solo el conocimiento.
8. Los agentes aplican ese manual al video propio.

Ollama consulta ese manual, sin necesidad de reentrenar el modelo. Aprende la forma de
editar, sin copiar guiones, voces ni material. Queda pendiente revisar cómo analizar los
videos respetando las condiciones de YouTube.

## 3. Agentes (propuesta)

| Agente | Responsabilidad |
|---|---|
| Analista | Estudia los videos y crea las fichas |
| Guionista | Trabaja la trama, introducción, narración y chistes |
| Editor | Hace cortes, transiciones y efectos |
| Memes y sonido | Coloca memes, stickers, música y efectos |
| Voz | Genera la narración con el tono de cada escena |
| Revisor | Compara con el manual y comprueba la continuidad |

## 4. Voces

- No se quieren voces locales.
- Hay que buscar voces en internet o en otro servicio que encajen en tono y expresión
  y no aburran.
- Catálogo propio de **máximo 4 voces**.
- Se escuchan antes de elegir.
- Deben ser gratuitas y permitir su uso en el canal.

## 5. Revisión por partes

- La aplicación entrega el resumen dividido; por ejemplo, 20 minutos en 10 partes de 2 minutos.
- Cada parte tiene **check** o **X**, y un comentario opcional.
- Rehace **solo las partes con X**, coordinando con la anterior y la siguiente.
- **Aprende los gustos de Jhon** con sus respuestas.
- **No hay conversación con la IA**: solo botones y comentarios.

## 6. Resultado esperado

Un video completo con el mismo estilo y calidad que los videos estudiados —trama, narración,
tono, cortes, transiciones, memes y sonido— pero con contenido propio.

## 7. Cómo avanzar

1. Estudiar **un video** y revisar su ficha.
2. Comparar las voces.
3. Editar **2 minutos** de un resumen propio y comprobar qué se parece y qué falta.
4. Si el resultado convence, construir la aplicación y completar los 30 videos.

El parecido exacto no está garantizado; la prueba mostrará hasta dónde se puede llegar.
