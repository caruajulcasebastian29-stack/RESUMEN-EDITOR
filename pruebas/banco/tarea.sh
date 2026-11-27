#!/usr/bin/env bash
# Tarea actual del banco: comparar modelos de visión sobre una película libre.
set -u
python -m pip install -q --upgrade pip
python -m pip install -q torch --index-url https://download.pytorch.org/whl/cpu
python -m pip install -q transnetv2-pytorch ffmpeg-python pydantic numpy
python pruebas/banco/pelicula_libre.py /tmp/pelicula.mp4 || exit 1
python -m pruebas.banco.vision /tmp/pelicula.mp4 qwen3-vl:4b qwen3.5:4b gemma3:4b
