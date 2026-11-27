# Comparativa de videos de referencia

Se actualiza con cada video analizado. Todo lo que figura aquí está medido o lo he visto en las hojas de fotogramas.

| | Video 1 | Video 2 | Video 3 | Video 4 | Video 5 | Video 6 |
|---|---|---|---|---|---|---|
| Canal | @EnMinutos | @EnMinutos | @EnMinutos | @EnMinutos | @EnMinutos | FERDAN |
| Película | *Burn* (2019) | *Babygirl* (2024) | *La Adolescente* (1979) | *Soulmate* | *La guerra de los últimos* | *Vertigo* |
| Duración | 23:34 | 22:13 | 26:09 | 26:28 | 25:03 | 29:52 (≈29 min sin anuncios) |
| Cortes por minuto | 30,4 | 30,1 | 22,7 | 25,9 | 32,0 | 35,0 |
| Plano mediano | 1,7 s | 1,9 s | 2,1 s | 2,2 s | 2,0 s | 1,6 s |
| Cortes relámpago (< 0,4 s) | 17 | 6 | 1 | 9 | 76 | 19 |
| Palabras por minuto | 221 | 209 | 201 | 183 | 186 | 184 |
| Voz | 98 % | 100 % | 97 % | 96 % | 96 % | 97 % |
| Pausas regulares del narrador | 25, cada ~54 s, ~1,1 s | ninguna | 23, cada ~66 s, ~1,7 s | 26, cada ~68 s, ~2,0 s | 25, cada ~64 s, ~2,1 s | ninguna (9 en total) |
| Fondo bajo la voz | ~12 dB menos | — | ~20 dB menos | ~17 dB menos | ~13 dB menos | ~5 dB (solo 9 pausas) |
| Volumen medio | -20,8 dB | -20,7 dB | -17,4 dB | -20,7 dB | -17,5 dB | -19,1 dB |
| Gancho | Clímax con cortes relámpago, 17 s | Diálogo original 5 s + sinopsis | Pregunta + premisa, 24 s | Diálogo original 11 s + pregunta + premisa, 36 s | Diálogo original 21 s + premisa, 36 s | Premisa narrada 28 s + chiste |
| Título | Tarjeta «BURN» + «Esto es…» | No | Solo dicho | Solo dicho | Dicho + tarjeta «LA GUERRA DE LOS ÚLTIMOS» | Solo dicho |
| Rótulos de personaje | Sí | No | No | Sí | No | Sí |
| Subtítulos animados | No | Sí, por tramos | No | No | No | No; frases en jerga arriba |
| Mensaje de miembros | No | No | Inicio y final, con lista | Inicio y final, con lista | Inicio y final, con lista | No; anuncio de su otro canal (31 s) |
| Like y suscripción | No | No | No | No | Sí, al final | Sí, al final, con el narrador en persona |
| Frase de cierre | — | — | — | «Nos vemos en el próximo Resumen Brutal» | «Nos vemos en el próximo resumen brutal de En Minutos» | «¿Ya te suscribiste?» |
| Censura | Difuminado parcial | Rectángulos pixelados | Difuminado total 21 s | No | No | Sangre pixelada |
| Imagen alterada | No | Apagada; 2 planos boca abajo | No | Muchos planos espejados | Muchos planos espejados | Blanco y negro tras el muñeco; tinte rojo |
| Clips de reacción / memes | **No** | **No** | **No** | **No** | **No** | **Sí**: memes de TV y muñeco del narrador |
| Transiciones | Solo cortes | Solo cortes | Cortes y fundidos | Solo cortes | Solo cortes | Solo cortes + tarjetas amarillas de tiempo |

## Lo que se repite en los cinco de @EnMinutos

- Narración casi continua, de 180 a 220 palabras por minuto.
- Cortes directos cada 2 s más o menos; reciclaje de planos cuando falta material.
- El ritmo sube en la acción (40–60 cortes por minuto) y baja en los diálogos (20–30).
- Marca de agua fija arriba a la derecha.
- El gancho usa planos de toda la película, incluido el clímax, antes de contar nada.
- Ningún meme ni clip de reacción.

## Lo que cambia con FERDAN (video 6)

- Más rápido: 35 cortes por minuto.
- Humor encima de la imagen: muñeco del narrador con la película en blanco y negro, frases en jerga arriba de las caras y memes de TV peruana.
- Tarjetas amarillas grandes para cada salto de tiempo («MÁS TARDE», «A LA MAÑANA SIGUIENTE»…).
- Sin la pausa regular de cada minuto.
- Palabras suavizadas («desvivir» en vez de morir).
- Publicidad de su otro canal (06:21–06:53) y pedido de suscripción al final: se excluyen.

Detalle en `video-06-ferdan-vertigo/observaciones.md`.

## Cambios que se ven en el canal

- Los videos 3, 4 y 5 añaden el mensaje de membresía al inicio y al final, con la lista de miembros en pantalla.
- Los videos 4 y 5 cierran con la misma frase y tienen muchos planos espejados.
- En cuatro de los cinco el narrador hace una pausa de 1 a 2 s cada minuto, más o menos.

## Cómo se midieron los cortes

Detector adaptativo (PySceneDetect) y, en los planos de más de 6 s que son oscuros, una segunda revisión
más sensible. Comprobado mirando las imágenes en los seis videos.
