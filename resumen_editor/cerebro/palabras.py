"""Capa 3 · Palabras: qué se dice, cuándo y quién lo dice.

1. Se transcribe la pista de voz ya separada de la música (mejor precisión) con Whisper turbo,
   por tramos de voz detectados con Silero VAD.
2. Se separan hablantes (pyannote-segmentation + huella de voz WeSpeaker). El hablante con más
   tiempo es el narrador; los demás son diálogos de la película que el canal dejó sonar.
3. Cada palabra recibe un tiempo aproximado (repartido dentro de su tramo según su largo).
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

from . import whisper_util as A
from . import modelos

TROZO_MAX_S = 18.0


def _leer16k(ruta: Path):
    import subprocess
    datos = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(ruta), "-ac", "1", "-ar", "16000",
                            "-f", "f32le", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(datos, np.float32).copy(), 16000


def _tramos_voz(a, sr) -> list[list[float]]:
    import sherpa_onnx
    cfg = sherpa_onnx.VadModelConfig()
    cfg.silero_vad.model = str(modelos.ruta("vad"))
    cfg.silero_vad.min_silence_duration = 0.25
    cfg.silero_vad.min_speech_duration = 0.25
    cfg.silero_vad.max_speech_duration = 20
    cfg.sample_rate = sr
    vad = sherpa_onnx.VoiceActivityDetector(cfg, buffer_size_in_seconds=120)
    tramos = []

    def vaciar():
        while not vad.empty():
            s = vad.front
            tramos.append([round(s.start / sr, 2), round((s.start + len(s.samples)) / sr, 2)])
            vad.pop()

    win = cfg.silero_vad.window_size
    for i in range(0, len(a), win):
        vad.accept_waveform(a[i:i + win])
        vaciar()
    vad.flush()
    vaciar()
    partidos = []
    for ini, fin in tramos:
        n = max(1, int(math.ceil((fin - ini) / TROZO_MAX_S)))
        bordes = [ini] + [A.punto_callado(a, sr, ini, fin, ini + k * (fin - ini) / n) for k in range(1, n)] + [fin]
        partidos += [[bordes[i], bordes[i + 1]] for i in range(n)]
    return partidos


def _hablantes(a, sr) -> list[tuple[float, float, int]]:
    import sherpa_onnx
    seg = modelos.ruta("segmentacion") / "model.onnx"
    cfg = sherpa_onnx.OfflineSpeakerDiarizationConfig(
        segmentation=sherpa_onnx.OfflineSpeakerSegmentationModelConfig(
            pyannote=sherpa_onnx.OfflineSpeakerSegmentationPyannoteModelConfig(model=str(seg))),
        embedding=sherpa_onnx.SpeakerEmbeddingExtractorConfig(model=str(modelos.ruta("huella_voz"))),
        clustering=sherpa_onnx.FastClusteringConfig(num_clusters=-1, threshold=0.6),
        min_duration_on=0.3, min_duration_off=0.5)
    d = sherpa_onnx.OfflineSpeakerDiarization(cfg)
    r = d.process(a).sort_by_start_time()
    return [(s.start, s.end, s.speaker) for s in r]


def _palabras(texto: str, ini: float, fin: float) -> list[dict]:
    p = texto.split()
    if not p:
        return []
    pesos = np.array([len(x) + 1 for x in p], float)
    bordes = ini + (fin - ini) * np.r_[0, np.cumsum(pesos)] / pesos.sum()
    return [{"p": w, "i": round(float(bordes[k]), 2), "f": round(float(bordes[k + 1]), 2)} for k, w in enumerate(p)]


def analizar(voz: Path, carpeta: Path, idioma: str = "es", aviso=None) -> dict:
    destino = carpeta / "palabras.json"
    if destino.exists():
        return json.loads(destino.read_text(encoding="utf-8"))
    import sherpa_onnx
    a, sr = _leer16k(voz)
    tramos = _tramos_voz(a, sr)
    w = modelos.ruta("whisper", aviso)
    rec = sherpa_onnx.OfflineRecognizer.from_whisper(
        encoder=str(w / "turbo-encoder.int8.onnx"), decoder=str(w / "turbo-decoder.int8.onnx"),
        tokens=str(w / "turbo-tokens.txt"), language=idioma, task="transcribe", num_threads=4)
    hechos = []
    for k, (s, e) in enumerate(tramos):
        hechos.append({"inicio": s, "fin": e, "texto": A.decodificar(rec, a, sr, s, e)})
        if aviso and k % 10 == 0:
            aviso("Transcribiendo", 100 * k / max(1, len(tramos)))
    A.reparar_bucles(rec, a, sr, hechos)

    try:
        hab = _hablantes(a, sr)
    except Exception as e:  # sin separación de hablantes, todo se toma como narrador
        hab, error = [], repr(e)
    else:
        error = None
    tiempo: dict[int, float] = {}
    for s, e, h in hab:
        tiempo[h] = tiempo.get(h, 0) + e - s
    narrador = max(tiempo, key=tiempo.get) if tiempo else None
    for h in hechos:
        votos: dict[int, float] = {}
        for s, e, sp in hab:
            solape = min(e, h["fin"]) - max(s, h["inicio"])
            if solape > 0:
                votos[sp] = votos.get(sp, 0) + solape
        quien = max(votos, key=votos.get) if votos else narrador
        h["hablante"] = "narrador" if quien == narrador else f"voz_{quien}"
        h["palabras"] = _palabras(h["texto"], h["inicio"], h["fin"])
    texto_narrador = " ".join(h["texto"] for h in hechos if h["hablante"] == "narrador")
    minutos_voz = sum(h["fin"] - h["inicio"] for h in hechos if h["hablante"] == "narrador") / 60
    datos = {"tramos": hechos, "hablantes": len(tiempo), "error_hablantes": error,
             "palabras_por_minuto": round(len(texto_narrador.split()) / minutos_voz, 1) if minutos_voz else 0}
    destino.write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")
    return datos
