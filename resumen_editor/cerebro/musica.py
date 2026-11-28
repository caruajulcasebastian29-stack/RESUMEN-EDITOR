"""Capa · Música, efectos de sonido y volumen.

Trabaja sobre la pista sin narrador que dejó la separación (musica.wav) y sobre la mezcla original:
  - ritmo de la música (pulsos por minuto) y si los cortes caen sobre el pulso (comparado con el azar)
  - cambios de música (dónde entra otra canción o cambia la parte) y si coinciden con un corte
  - cómo se mueve el volumen de la música: sube en las pausas del narrador, baja cuando habla
  - efectos de sonido: golpes y «whoosh» cortos que sobresalen de la música, y cuántos caen en un corte
  - volumen real (LUFS, la medida de YouTube) de la mezcla, la voz y la música
Usa librosa y el medidor de volumen de FFmpeg (gratis, sin internet).
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import numpy as np

SR = 22050


def _leer(ruta: Path, sr: int = SR, canales: int = 1) -> np.ndarray:
    datos = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(ruta), "-vn", "-ac", str(canales), "-ar", str(sr),
                            "-f", "f32le", "-"], capture_output=True, check=True).stdout
    a = np.frombuffer(datos, np.float32).copy()
    return a.reshape(-1, canales) if canales > 1 else a


def _lufs(ruta: Path) -> float | None:
    """Volumen integrado (LUFS, la medida que usa YouTube) con el filtro ebur128 de FFmpeg."""
    import re
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(ruta), "-vn", "-af", "ebur128=framelog=quiet",
                        "-f", "null", "-"], capture_output=True, text=True)
    m = re.findall(r"I:\s+(-?[\d.]+) LUFS", r.stderr)
    return float(m[-1]) if m else None


def _cerca(tiempos: np.ndarray, marcas: np.ndarray, tol: float) -> float:
    """Fracción de `tiempos` que tiene alguna marca a menos de `tol` segundos."""
    if not len(tiempos) or not len(marcas):
        return 0.0
    idx = np.clip(np.searchsorted(marcas, tiempos), 1, len(marcas) - 1)
    d = np.minimum(np.abs(tiempos - marcas[idx - 1]), np.abs(tiempos - marcas[idx]))
    return float((d <= tol).mean())


def analizar(video: Path, carpeta: Path, tomas: list[dict], audio: dict, dur: float, aviso=None) -> dict:
    destino = carpeta / "musica.json"
    if destino.exists():
        return json.loads(destino.read_text(encoding="utf-8"))
    import librosa
    if aviso:
        aviso("Escuchando la música", 0)
    m = _leer(carpeta / "musica.wav")
    cortes = np.array([t["inicio"] for t in tomas[1:]], float)

    # 1. pulso y cortes al compás
    tempo, beats = librosa.beat.beat_track(y=m, sr=SR, units="time")
    tempo = float(np.atleast_1d(tempo)[0])
    beats = np.asarray(beats, float)
    al_pulso = _cerca(cortes, beats, 0.07)
    rng = np.random.default_rng(0)
    azar = float(np.mean([_cerca(np.sort(rng.uniform(0, dur, len(cortes))), beats, 0.07) for _ in range(5)])) if len(cortes) else 0

    if aviso:
        aviso("Buscando cambios de música", 30)
    # 2. cambios de música: novedad en el timbre/armonía, picos separados al menos 8 s
    hop = 2048
    cro = librosa.feature.chroma_cqt(y=m, sr=SR, hop_length=hop)
    mf = librosa.feature.mfcc(y=m, sr=SR, n_mfcc=13, hop_length=hop)
    rasgos = np.vstack([librosa.util.normalize(cro, axis=0), librosa.util.normalize(mf, axis=1)])
    paso = int(4 * SR / hop)  # 4 s antes y después
    nov = np.zeros(rasgos.shape[1])
    for i in range(paso, rasgos.shape[1] - paso):
        nov[i] = np.linalg.norm(rasgos[:, i - paso:i].mean(1) - rasgos[:, i:i + paso].mean(1))
    picos = librosa.util.peak_pick(nov, pre_max=paso, post_max=paso, pre_avg=paso * 2, post_avg=paso * 2,
                                   delta=float(np.std(nov)) * 0.8, wait=int(8 * SR / hop))
    cambios = librosa.frames_to_time(picos, sr=SR, hop_length=hop)
    rms_m = librosa.feature.rms(y=m, hop_length=hop)[0]
    hay_musica = rms_m > np.percentile(rms_m, 95) * 0.05
    cambios = np.array([c for c in cambios if hay_musica[min(len(hay_musica) - 1, int(c * SR / hop))]])

    if aviso:
        aviso("Buscando efectos de sonido", 55)
    # 3. efectos: golpes cortos que sobresalen mucho de la música y no caen en el pulso
    on_env = librosa.onset.onset_strength(y=m, sr=SR)
    on = librosa.onset.onset_detect(onset_envelope=on_env, sr=SR, units="time", backtrack=False)
    fuerza = on_env[librosa.time_to_frames(on, sr=SR)] if len(on) else np.array([])
    umbral = np.percentile(on_env, 99.5) if len(on_env) else 0
    golpes = np.array([t for t, f in zip(on, fuerza) if f >= umbral])
    if len(golpes) and len(beats):
        golpes = golpes[[_cerca(np.array([g]), beats, 0.05) == 0 for g in golpes]]
    efectos_en_corte = _cerca(golpes, cortes, 0.15)

    # 4. la música sube cuando el narrador calla
    pausas = audio.get("pausas", {}).get("lista", [])
    t_rms = librosa.frames_to_time(np.arange(len(rms_m)), sr=SR, hop_length=hop)
    en_pausa = np.zeros(len(rms_m), bool)
    for a, b in pausas:
        en_pausa |= (t_rms >= a) & (t_rms <= b)
    db = 20 * np.log10(rms_m + 1e-7)
    sube = float(np.median(db[en_pausa & hay_musica]) - np.median(db[~en_pausa & hay_musica])) \
        if (en_pausa & hay_musica).any() and (~en_pausa & hay_musica).any() else None

    if aviso:
        aviso("Midiendo el volumen", 85)
    # 5. volumen real
    lufs = {"mezcla": _lufs(video), "voz": _lufs(carpeta / "voz.wav"), "musica": _lufs(carpeta / "musica.wav")}

    minutos = max(dur / 60, 0.1)
    datos = {
        "pulsos_por_minuto": round(tempo, 1),
        "cortes_al_pulso": round(al_pulso, 2), "cortes_al_pulso_si_fuera_azar": round(azar, 2),
        "corta_al_compas": bool(len(cortes) > 20 and al_pulso > azar + 0.1),
        "cambios_de_musica": [round(float(c), 1) for c in cambios],
        "cambios_por_minuto": round(len(cambios) / minutos, 2),
        "cambios_en_corte": round(_cerca(cambios, cortes, 0.5), 2),
        "musica_sube_en_pausas_db": round(sube, 1) if sube is not None else None,
        "efectos": [round(float(g), 2) for g in golpes],
        "efectos_por_minuto": round(len(golpes) / minutos, 2),
        "efectos_en_corte": round(efectos_en_corte, 2),
        "lufs": lufs,
    }
    destino.write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")
    return datos


def resumen(d: dict) -> dict:
    return {k: d[k] for k in ("pulsos_por_minuto", "cortes_al_pulso", "cortes_al_pulso_si_fuera_azar", "corta_al_compas",
                              "cambios_por_minuto", "cambios_en_corte", "musica_sube_en_pausas_db", "efectos_por_minuto",
                              "efectos_en_corte", "lufs")}
