#!/usr/bin/env bash
# Tarea actual del banco: el cerebro completo de la versión 0.3.0 con Ollama de verdad
# (estudio + examen + modelo propio, personaje, aprender un video con todas las capas, preguntas).
# La tarea anterior (animar el mapache) queda en el historial del repositorio.
set -u
mkdir -p salida/cerebro
export RESUMEN_EDITOR_DATOS=/tmp/datos RESUMEN_EDITOR_MODELOS=$HOME/modelos
# en el servidor de pruebas el modelo de 9B es muy lento: el perfil lo escribe el de 4B
export RE_MODELO_ESCRITOR=qwen3:4b-instruct
python -m pip install -q --upgrade pip
python -m pip install -q torch --index-url https://download.pytorch.org/whl/cpu
python -m pip install -q -r instalador/requirements-windows.txt 2>&1 | tail -3
python -m pip install -q $(grep -v '^#' resumen_editor/complementos.txt | awk '{print $1}' | grep -v '^$') 2>&1 | tail -3
python -c "import rapidocr_onnxruntime, parselmouth, sherpa_onnx, lancedb, cv2; print('dependencias ok')"

# un fragmento de 3 minutos de una película de dominio público, como «video de referencia»
python pruebas/banco/pelicula_libre.py /tmp/peli.mp4 && \
  ffmpeg -v error -y -ss 600 -t 180 -i /tmp/peli.mp4 -c:v libx264 -preset veryfast -crf 24 -c:a aac /tmp/ref.mp4

python pruebas/banco/cerebro.py estudio 2>&1 | grep -v Warning
python pruebas/banco/cerebro.py personaje 2>&1 | grep -v Warning
[ -f /tmp/ref.mp4 ] && python pruebas/banco/cerebro.py video /tmp/ref.mp4 2>&1 | grep -v -i "warning\|it/s\]"
python pruebas/banco/cerebro.py preguntas 2>&1 | grep -v Warning
ollama list
