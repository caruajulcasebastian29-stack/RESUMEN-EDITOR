"""Modelos que la app descarga sola la primera vez (todos gratuitos, desde las publicaciones de sherpa-onnx).

Se guardan en la carpeta de datos de la app; si ya están, no se vuelven a bajar.
"""
from __future__ import annotations

import os
import tarfile
import urllib.request
from pathlib import Path

CARPETA = Path(os.environ.get("RESUMEN_EDITOR_MODELOS", Path.home() / "modelos"))
BASE = "https://github.com/k2-fsa/sherpa-onnx/releases/download"

CATALOGO = {
    # nombre: (url, archivo o carpeta que debe existir al terminar)
    "whisper": (f"{BASE}/asr-models/sherpa-onnx-whisper-turbo.tar.bz2", "sherpa-onnx-whisper-turbo"),
    "vad": (f"{BASE}/asr-models/silero_vad.onnx", "silero_vad.onnx"),
    "segmentacion": (f"{BASE}/speaker-segmentation-models/sherpa-onnx-pyannote-segmentation-3-0.tar.bz2",
                     "sherpa-onnx-pyannote-segmentation-3-0"),
    "huella_voz": (f"{BASE}/speaker-recongition-models/wespeaker_en_voxceleb_resnet34_LM.onnx",
                   "wespeaker_en_voxceleb_resnet34_LM.onnx"),
    # qué se oye: risas, gritos, golpes, ánimo de la música (527 clases de AudioSet)
    "sonidos": (f"{BASE}/audio-tagging-models/sherpa-onnx-ced-mini-audio-tagging-2024-04-19.tar.bz2",
                "sherpa-onnx-ced-mini-audio-tagging-2024-04-19"),
    # caras en pantalla, para saber si la toma es primer plano o plano general (OpenCV, YuNet)
    "caras": ("https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/face_detection_yunet/"
              "face_detection_yunet_2023mar.onnx", "face_detection_yunet_2023mar.onnx"),
}


def ruta(nombre: str, aviso=None) -> Path:
    url, final = CATALOGO[nombre]
    destino = CARPETA / final
    if destino.exists():
        return destino
    CARPETA.mkdir(parents=True, exist_ok=True)
    temporal = CARPETA / (Path(url).name + ".parcial")

    def progreso(bloques, tam, total):
        if aviso and total > 0:
            aviso(f"Descargando modelo {nombre}", min(100, 100 * bloques * tam / total))

    urllib.request.urlretrieve(url, temporal, progreso)
    if url.endswith(".tar.bz2"):
        with tarfile.open(temporal) as t:
            t.extractall(CARPETA, filter="data")
        temporal.unlink()
    else:
        temporal.rename(destino)
    return destino
