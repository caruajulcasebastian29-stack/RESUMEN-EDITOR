#!/usr/bin/env bash
# Tarea del banco: cerebro 0.3.0, segunda prueba.
# Antes de probar aplica pruebas/parches/arreglos.patch (los arreglos de la primera prueba). Si todas las
# pruebas pasan, deja esos arreglos guardados en main; si alguna falla, no toca main.
set -u
mkdir -p salida/cerebro
git apply --whitespace=nowarn pruebas/parches/arreglos.patch && echo "parche aplicado" || { echo "EL PARCHE NO APLICA"; exit 1; }
export RESUMEN_EDITOR_DATOS=/tmp/datos RESUMEN_EDITOR_MODELOS=$HOME/modelos
export RE_MODELO_ESCRITOR=qwen3:4b-instruct   # en el servidor de pruebas el de 9B es muy lento
python -m pip install -q --upgrade pip
python -m pip install -q torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
python -m pip install -q -r instalador/requirements-windows.txt 2>&1 | tail -3
# que pip no cambie torch/torchvision por las versiones con tarjeta gráfica
python -m pip install -q --force-reinstall --no-deps torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
python -m pip install -q $(grep -v '^#' resumen_editor/complementos.txt | awk '{print $1}' | grep -v '^$') 2>&1 | tail -3
python -c "import rapidocr_onnxruntime, parselmouth, sherpa_onnx, lancedb, cv2, torchvision; print('dependencias ok', torchvision.__version__)"

python pruebas/banco/pelicula_libre.py /tmp/peli.mp4 && \
  ffmpeg -v error -y -ss 600 -t 180 -i /tmp/peli.mp4 -c:v libx264 -preset veryfast -crf 24 -c:a aac /tmp/ref.mp4

fallos=0
paso() { python pruebas/banco/cerebro.py "$@" 2>&1 | grep -v -i "warning\|it/s\]\|iB/s\]"; r=${PIPESTATUS[0]}; [ "$r" = 0 ] || { echo "!! FALLÓ: $1"; fallos=$((fallos+1)); }; }
paso estudio
paso personaje
paso video /tmp/ref.mp4
paso preguntas
ollama list
echo "== fallos: $fallos"
if [ "$fallos" = 0 ]; then
  git config user.name "caruajulcasebastian29-stack"
  git config user.email "caruajulcasebastian29@gmail.com"
  git add resumen_editor pruebas/banco/componer.py
  git commit -q -m "Cerebro: arreglos probados en el banco (tope de largo en las respuestas, examen que no se cae, perfil del personaje con sentido)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_013161zHSZBE4nQwTJKom1uG" && git push -q origin HEAD:main && echo "arreglos guardados en main"
fi
