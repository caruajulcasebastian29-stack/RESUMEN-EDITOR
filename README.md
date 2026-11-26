# RESUMEN-EDITOR — App 2 de Resumen Labs

Toma un resumen de película ya producido (el que entrega **RESUMEN-LABS**, la App 1) y lo
reescribe y reedita con el estilo aprendido de videos de referencia, para que no salga aburrido.

## Cómo trabajamos aquí

Jhon no abre una terminal en ningún momento del proceso.

| Quién | Qué hace |
|---|---|
| Claude | Escribe y corrige el código en este repositorio, y publica el instalador en *Releases*. |
| Jhon | Descarga el instalador, lo abre con doble clic y trabaja en la ventana de la aplicación. |

Todo lo que hoy requiere escribir comandos queda del lado del repositorio, no del lado de Jhon.

## Estado

| Parte | Estado |
|---|---|
| Especificación del proyecto | Escrita — `docs/01-especificacion.md` |
| Plan técnico y arquitectura | Escrito — `docs/02-plan-tecnico.md` |
| Plantillas de análisis | Escritas — `docs/04-plantillas.md` |
| Prototipo de interfaz | Hecho — siete pantallas navegables, publicado como artifact |
| Selección de voces | **Aplazada** por decisión de Jhon. Enfoque y motor decididos en `docs/03-voces.md`; falta escuchar y elegir las 4 |
| Código de la aplicación | No empezado |

## El prototipo de interfaz

Siete pantallas, todas funcionando con datos de ejemplo:

| Pantalla | Qué resuelve |
|---|---|
| Inicio | Estado del resumen cargado y avance de la revisión |
| Videos de referencia | Añadir videos uno por uno y ver la ficha medida de cada uno |
| Manual de estilo | Las reglas salidas de las fichas, corregibles a mano |
| Mis preferencias | Se llena solo con cada ✓ y ✗ de la revisión |
| Revisión por lotes | La pantalla central: 10 lotes de 2 min con ✓/✗, comentario y rehacer solo los marcados |
| Voces | Cuatro puestos reservados, sin asignar todavía |
| Exportar | Bloqueado hasta que los diez lotes estén aprobados |

Sirve para decidir el funcionamiento antes de escribir código. Lo que se apruebe ahí es lo
que se construye.

## Bloqueo conocido

La App 1 entrega hoy un MP4 terminado. Con un MP4 no se puede rehacer un solo lote, porque
dentro ya no existen el guion, los clips ni el audio por frase. **La App 1 tiene que exportar
la carpeta del proyecto.** Es el primer cambio pendiente y está explicado en el punto 1 del
plan técnico.

## Documentos

1. **[Especificación](docs/01-especificacion.md)** — el proyecto tal como lo planteó Jhon, ordenado.
2. **[Plan técnico](docs/02-plan-tecnico.md)** — arquitectura, qué se automatiza y qué no, y por qué.
3. **[Voces](docs/03-voces.md)** — diseño de voz, motores comparados y derechos de uso.
4. **[Plantillas](docs/04-plantillas.md)** — ficha por video y esquema del manual de estilo.

## Regla del proyecto

Todas las herramientas deben ser gratuitas. Si una pieza solo funciona pagando, se descarta
y se busca reemplazo libre, o se elimina del alcance.
