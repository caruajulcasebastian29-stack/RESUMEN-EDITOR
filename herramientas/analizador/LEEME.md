# Analizador de videos de referencia

Analiza cada video sin que nadie transcriba ni mire nada a mano. Corre en el espacio de
trabajo de Claude; no usa ningún servicio externo.

## Qué saca de cada video

| Archivo | Contenido | Cómo se obtiene |
|---|---|---|
| `cortes.json` | Cada corte y la duración de cada plano | Medido sobre la imagen |
| `hojas/minuto_XX.jpg` | Un fotograma por plano, rotulado con su segundo | Para que Claude los mire |
| `transcripcion.json` | Lo que se dice, por tramos, con inicio y fin | Whisper turbo, local |
| `audio_segundos.json` | Volumen por segundo y silencios | Medido sobre la onda |
| `ficha.json` / `resumen.md` | Todo junto, más candidatos a clip de reacción | Calculado |

## Cómo se usa

Lo usa Claude, no Jhon:

```
bash herramientas/analizador/instalar.sh          # una vez por sesión, tarda ~1 min la primera
python3 herramientas/analizador/analizar_video.py VIDEO
python3 herramientas/analizador/analizar_video.py --lote CARPETA
```

Jhon solo deja los videos en una carpeta de su computadora conectada a la sesión. Claude los
trae, los analiza y mira las hojas de fotogramas.

## Detalles que importan

- **Se reanuda solo.** Cada etapa guarda su resultado. Si un video se corta a mitad, al volver
  a lanzarlo sigue donde quedó. En modo lote salta los ya analizados.
- **Candidatos a clip de reacción.** Marca los planos de 1 a 7 segundos durante los cuales el
  narrador casi no habla: la firma de «se corta todo, entra un clip, vuelve». Son candidatos;
  se confirman mirando la hoja de fotogramas.
- **Videos verticales.** Las miniaturas aceptan cualquier proporción.
- **Tamaño.** Para traer un video desde la computadora el límite es de 400 MB por archivo.
  A 720p un resumen de 20 minutos entra de sobra.
- **Velocidad.** La transcripción va a unas 2,5 veces el tiempo real: un video de 22 minutos
  tarda unos 9 minutos en total.

## Prueba de validación (26 nov 2026)

Video sintético de 12,24 s con cortes en posiciones conocidas, narración en español y un
«clip» de 3 s sin narrador en medio.

| Qué | Esperado | Medido |
|---|---|---|
| Cortes | 3,00 · 5,85 · 8,85 | 3,00 · 5,84 · 8,84 |
| Silencio del clip | 5,85 – 8,85 | 5,70 – 8,90 |
| Transcripción | Dos frases en español | Las dos, palabra por palabra |
| Candidatos a clip | El plano 3 | Solo el plano 3, con el narrador al 0 % |
