"""Capa 2 · Audio: separa la voz del narrador de la música y mide cómo se mezclan.

Separación con audio-separator (modelos de Ultimate Vocal Remover). Mide:
  - cuánto suena la música debajo de la voz y cuánto sube cuando la voz calla
  - qué parte del video lleva música
  - silencios de la voz (pausas de respiración, pausas dramáticas)
Las pistas separadas quedan en la carpeta de la ficha para las capas siguientes.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import numpy as np

MODELO_SEPARACION = "UVR-MDX-NET-Voc_FT.onnx"
CARPETA_MODELOS = Path(os.environ.get("RESUMEN_EDITOR_MODELOS", Path.home() / "modelos")) / "separacion"
SR = 16000
VENTANA = 0.1  # segundos por medida de volumen


def separar(video: Path, carpeta: Path) -> tuple[Path, Path]:
    voz, musica = carpeta / "voz.wav", carpeta / "musica.wav"
    if voz.exists() and musica.exists():
        return voz, musica
    mezcla = carpeta / "mezcla.wav"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(video), "-vn", "-ac", "2", "-ar", "44100",
                    str(mezcla)], check=True)
    from audio_separator.separator import Separator
    CARPETA_MODELOS.mkdir(parents=True, exist_ok=True)
    sep = Separator(output_dir=str(carpeta), model_file_dir=str(CARPETA_MODELOS), log_level=40)
    sep.load_model(MODELO_SEPARACION)
    for nombre in sep.separate(str(mezcla)):
        ruta = carpeta / Path(nombre).name
        ruta.rename(voz if "(Vocals)" in nombre else musica)
    mezcla.unlink(missing_ok=True)
    return voz, musica


def niveles(ruta: Path) -> np.ndarray:
    """Volumen en dB cada VENTANA segundos."""
    datos = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(ruta), "-ac", "1", "-ar", str(SR),
                            "-f", "f32le", "-"], capture_output=True, check=True).stdout
    a = np.frombuffer(datos, np.float32)
    n = int(SR * VENTANA)
    a = a[: len(a) // n * n].reshape(-1, n)
    return 20 * np.log10(np.sqrt((a ** 2).mean(1)) + 1e-7)


def tramos(mascara: np.ndarray, minimo: float) -> list[list[float]]:
    salida, ini = [], None
    for i, m in enumerate(np.r_[mascara, False]):
        if m and ini is None:
            ini = i
        elif not m and ini is not None:
            if (i - ini) * VENTANA >= minimo:
                salida.append([round(ini * VENTANA, 2), round(i * VENTANA, 2)])
            ini = None
    return salida


def analizar(video: Path, carpeta: Path) -> dict:
    destino = carpeta / "audio.json"
    if destino.exists():
        return json.loads(destino.read_text(encoding="utf-8"))
    voz, musica = separar(video, carpeta)
    dv, dm = niveles(voz), niveles(musica)
    n = min(len(dv), len(dm))
    dv, dm = dv[:n], dm[:n]
    habla = dv > np.percentile(dv, 95) - 12  # medido: la narración real queda 12 dB bajo su pico
    suena_musica = dm > np.percentile(dm, 95) - 30
    pausas = tramos(~habla, 0.15)
    largas = [p for p in pausas if p[1] - p[0] >= 0.6]
    bajo_voz = dm[habla & suena_musica]
    sin_voz = dm[~habla & suena_musica]
    datos = {
        "musica_presente": round(float(suena_musica.mean()), 2),
        "musica_bajo_voz_db": round(float(np.median(bajo_voz) - np.median(dv[habla])), 1) if bajo_voz.size else None,
        "musica_sube_sin_voz_db": round(float(np.median(sin_voz) - np.median(bajo_voz)), 1)
        if sin_voz.size and bajo_voz.size else None,
        "voz_activa": round(float(habla.mean()), 2),
        "pausas": {"cantidad": len(pausas), "largas": len(largas),
                   "mediana_s": round(float(np.median([p[1] - p[0] for p in pausas])), 2) if pausas else 0,
                   "lista": pausas},
    }
    destino.write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")
    return datos
