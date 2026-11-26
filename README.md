# RESUMEN-EDITOR — App 2 de Resumen Labs

Toma un resumen de película ya producido (el que entrega **RESUMEN-LABS**, la App 1) y lo
reescribe y reedita con el estilo aprendido de videos de referencia, para que no salga aburrido.

**Canal base:** @AsíPaso.

## Cómo trabajamos aquí

Jhon no abre una terminal en ningún momento del proceso.

| Quién | Qué hace |
|---|---|
| Claude | Escribe y corrige el código en este repositorio, y publica el instalador en *Releases*. |
| Jhon | Descarga el instalador, lo abre con doble clic y trabaja en la ventana de la aplicación. |

## Estado

| Parte | Estado |
|---|---|
| Especificación | Escrita |
| Plan técnico | Escrito y corregido el 26 nov |
| Pipeline de análisis | Definido y probado |
| Herramientas de análisis | letmewatch verificado de punta a punta. Local Whisper instalado como plugin, falta conectar el servidor |
| Manual de estilo de @AsíPaso | Primer borrador, con lo verificado separado de lo supuesto |
| Prototipo de interfaz | Ocho pantallas navegables, publicado como artifact |
| Selección de voces | Aplazada por decisión de Jhon. Enfoque y motor ya decididos |
| Código de la aplicación | No empezado |

## Bloqueos

1. **La App 1 entrega un MP4 terminado.** Con un MP4 no se puede rehacer un solo lote, porque
   dentro ya no existen el guion, los clips ni el audio por frase. Tiene que exportar la carpeta
   del proyecto. Es el primer cambio pendiente — punto 1 del plan técnico.
2. **Falta un archivo de video en una carpeta conectada** para correr el pipeline completo.

## Documentos

| # | Documento | Qué contiene |
|---|---|---|
| 01 | [Especificación](docs/01-especificacion.md) | El proyecto tal como lo planteó Jhon, ordenado |
| 02 | [Plan técnico](docs/02-plan-tecnico.md) | Arquitectura, recortes y orden de trabajo. Sus secciones 2, 5 y 8 están sustituidas por la 09 |
| 03 | [Voces](docs/03-voces.md) | Diseño de voz, motores comparados y derechos de uso |
| 04 | [Plantillas](docs/04-plantillas.md) | Ficha por video, manual de estilo y preferencias aprendidas |
| 05 | [Prueba manual](docs/05-prueba-manual.md) | Instrucción y esquema para analizar un bloque en AI Studio |
| 06 | [Análisis en dos niveles](docs/06-analisis-dos-niveles.md) | Por qué el video se mira dos veces: detalle y conjunto |
| 07 | [Resultado de la prueba](docs/07-resultado-prueba.md) | 60 entradas de 60. Qué campos sirvieron y cuáles fallaron |
| 08 | [Manual de estilo @AsíPaso](docs/08-manual-estilo-asipaso.md) | Reglas de narración, humor y montaje, con su estado de verificación |
| 09 | [Pipeline de análisis](docs/09-pipeline-analisis.md) | **Procedimiento vigente.** Quién mide qué y con qué herramienta |

## Dos principios que salieron de las pruebas

**Nada entra como supuesto.** Cada dato de las fichas lleva marcado si fue observado, medido o
razonado. La primera versión del manual venía de un análisis lleno de «posiblemente» y
«probablemente»; al comprobar el primer minuto contra el video, varias de esas afirmaciones
eran falsas.

**Ningún modelo opina sobre lo que no puede percibir.** El campo de energía de la voz venía
relleno sin que nada hubiera escuchado el audio. Lo que se oye se transcribe o se mide; lo que
se ve se mira.

## Regla del proyecto

Todas las herramientas deben ser gratuitas. Si una pieza solo funciona pagando, se descarta y se
busca reemplazo libre, o se elimina del alcance.
