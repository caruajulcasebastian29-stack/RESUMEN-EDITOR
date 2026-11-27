"""Capa 6 · Voz: cómo suena el narrador, medido frase por frase.

Por cada tramo del narrador: tono medio, cuánto sube y baja (semitonos), energía y velocidad.
Con esto la app sabe cuándo el narrador se acelera, grita o baja la voz, y más adelante puede
comprobar que una voz generada se mueve como las de referencia (una voz plana suena a robot).
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

SR = 16000


def _medir(a: np.ndarray) -> dict | None:
    import librosa
    if len(a) < SR * 0.6:
        return None
    f0, voiced, _ = librosa.pyin(a, fmin=60, fmax=700, sr=SR, frame_length=1024)
    f0 = f0[voiced & ~np.isnan(f0)]
    if len(f0) < 8:
        return None
    st = 12 * np.log2(f0 / np.median(f0))
    rms = np.sqrt(np.mean(a ** 2)) + 1e-7
    return {"tono_hz": round(float(np.median(f0)), 1),
            "rango_st": round(float(np.percentile(st, 95) - np.percentile(st, 5)), 1),
            "energia_db": round(float(20 * np.log10(rms)), 1)}


def analizar(voz: Path, carpeta: Path, palabras: dict) -> dict:
    destino = carpeta / "voz.json"
    if destino.exists():
        return json.loads(destino.read_text(encoding="utf-8"))
    from .palabras import _leer16k
    a, _ = _leer16k(voz)
    frases = []
    for t in palabras["tramos"]:
        if t["hablante"] != "narrador":
            continue
        m = _medir(a[int(t["inicio"] * SR):int(t["fin"] * SR)])
        if not m:
            continue
        dur = t["fin"] - t["inicio"]
        m.update({"inicio": t["inicio"], "fin": t["fin"],
                  "palabras_s": round(len(t["texto"].split()) / dur, 2) if dur else 0})
        frases.append(m)
    if frases:
        base = float(np.median([f["energia_db"] for f in frases]))
        for f in frases:  # frases mucho más fuertes que lo normal: posibles gritos o remates
            f["sobresale_db"] = round(f["energia_db"] - base, 1)
    resumen = {}
    if frases:
        def col(k):
            return np.array([f[k] for f in frases])
        resumen = {"tono_hz": round(float(np.median(col("tono_hz"))), 1),
                   "rango_st_mediana": round(float(np.median(col("rango_st"))), 1),
                   "rango_st_p90": round(float(np.percentile(col("rango_st"), 90)), 1),
                   "palabras_s": round(float(np.median(col("palabras_s"))), 2),
                   "variacion_energia_db": round(float(np.std(col("energia_db"))), 1),
                   "frases_que_sobresalen": int((col("sobresale_db") > 6).sum())}
    datos = {"frases": frases, "resumen": resumen}
    destino.write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")
    return datos
