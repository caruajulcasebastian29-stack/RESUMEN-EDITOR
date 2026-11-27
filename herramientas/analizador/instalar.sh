#!/usr/bin/env bash
# Deja listo el analizador en el espacio de trabajo de Claude.
# Es seguro ejecutarlo varias veces: lo que ya está instalado no se vuelve a bajar.
set -euo pipefail
cd "$(dirname "$0")"
REL=https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models

echo "1/3 Librerías…"
pip install --break-system-packages -q sherpa-onnx soundfile numpy pillow scenedetect opencv-python-headless 2>&1 | grep -v WARNING || true

mkdir -p modelos
echo "2/3 Whisper turbo (unos 560 MB la primera vez)…"
if [ ! -f modelos/sherpa-onnx-whisper-turbo/turbo-encoder.int8.onnx ]; then
  curl -sSL "$REL/sherpa-onnx-whisper-turbo.tar.bz2" | tar xj -C modelos
fi

echo "3/3 Detector de voz…"
if [ ! -f modelos/silero_vad.onnx ]; then
  curl -sSL -o modelos/silero_vad.onnx "$REL/silero_vad.onnx"
fi

python3 -c "import sherpa_onnx, soundfile, numpy, PIL, scenedetect, cv2" \
  && test -f modelos/sherpa-onnx-whisper-turbo/turbo-encoder.int8.onnx \
  && test -f modelos/silero_vad.onnx \
  && echo "LISTO: analizador instalado."
