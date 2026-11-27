"""Revisión por lotes de ~2 minutos con ✓ / ✗ y aprendizaje de gustos."""
from __future__ import annotations

from .config import estilo, guardar_preferencias, preferencias


def partir(duraciones: list[float]) -> list[list[int]]:
    """Agrupa frases (índices) en lotes de ~2 min, sin cortar frases y prefiriendo cortar tras una tarjeta/pausa."""
    cfg = estilo("montaje")["lotes"]
    lotes, actual, t = [], [], 0.0
    for i, d in enumerate(duraciones):
        actual.append(i)
        t += d
        if t >= cfg["duracion_s"]:
            lotes.append(actual)
            actual, t = [], 0.0
    if actual:
        if lotes and t < cfg["tolerancia_s"]:
            lotes[-1] += actual  # un resto muy corto se une al lote anterior
        else:
            lotes.append(actual)
    return lotes


def aprender(textos: list[str], aprobado: bool, comentario: str = "") -> None:
    """Guarda cada decisión para que el guionista la lea la próxima vez."""
    pref = preferencias()
    muestra = " ".join(textos)[:220]
    if aprobado:
        pref["aprobado"].append(f"Aprobado: «{muestra}»")
    else:
        pref["rechazado"].append(f"Rechazado{': ' + comentario if comentario else ''} → «{muestra}»")
    if comentario:
        pref["notas"].append(comentario)
    guardar_preferencias(pref)
