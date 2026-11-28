"""Capa · Ritmo: cómo se relacionan la velocidad de la voz, los cortes y la estructura del video.

Corta el video en ventanas de 10 s y mide en cada una palabras por segundo y cortes; de ahí sale si el editor
acelera los cortes cuando el narrador acelera, cómo cambia el ritmo a lo largo del video (inicio, medio, final)
y dónde están los tramos más rápidos y más lentos.
"""
from __future__ import annotations

import numpy as np

VENTANA = 10.0


def analizar(tomas: list[dict], palabras: dict, dur: float) -> dict:
    n = max(1, int(dur // VENTANA))
    cortes = np.zeros(n)
    for t in tomas[1:]:
        k = int(t["inicio"] // VENTANA)
        if k < n:
            cortes[k] += 1
    pal = np.zeros(n)
    for tr in palabras.get("tramos", []):
        if tr.get("hablante", "narrador") != "narrador":
            continue
        for p in tr.get("palabras", []):
            k = int(p["i"] // VENTANA)
            if k < n:
                pal[k] += 1
    cpm = cortes * 60 / VENTANA
    ppm = pal * 60 / VENTANA
    relacion = float(np.corrcoef(cpm, ppm)[0, 1]) if n > 4 and cpm.std() > 0 and ppm.std() > 0 else None
    tercios = np.array_split(np.arange(n), 3)
    por_parte = {nombre: {"cortes_por_minuto": round(float(cpm[idx].mean()), 1),
                          "palabras_por_minuto": round(float(ppm[idx].mean()), 1)}
                 for nombre, idx in zip(("inicio", "medio", "final"), tercios) if len(idx)}
    gancho = min(n, 3)  # primeros 30 s
    orden = np.argsort(cpm)
    return {
        "relacion_voz_cortes": round(relacion, 2) if relacion is not None else None,
        "por_parte": por_parte,
        "gancho_cortes_por_minuto": round(float(cpm[:gancho].mean()), 1),
        "resto_cortes_por_minuto": round(float(cpm[gancho:].mean()), 1) if n > gancho else None,
        "tramo_mas_rapido_s": [float(orden[-1] * VENTANA), float(orden[-1] * VENTANA + VENTANA)],
        "tramo_mas_lento_s": [float(orden[0] * VENTANA), float(orden[0] * VENTANA + VENTANA)],
        "variacion_cortes": round(float(cpm.std() / max(cpm.mean(), 1e-6)), 2),
    }
