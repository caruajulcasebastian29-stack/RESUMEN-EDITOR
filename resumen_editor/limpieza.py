"""Limpieza del video de origen: logo fijo del canal, tramos de autopromoción y pantalla final."""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import numpy as np

from .config import estilo


def duracion(video: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(video)],
                         capture_output=True, text=True, check=True).stdout
    return float(out.strip())


def tamano(video: Path) -> tuple[int, int]:
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
                          "-of", "csv=p=0", str(video)], capture_output=True, text=True, check=True).stdout
    w, h = out.strip().split(",")[:2]
    return int(w), int(h)


def _leer_fotogramas(video: Path, n: int, ancho: int = 480) -> np.ndarray:
    """n fotogramas en gris repartidos por todo el video: (n, alto, ancho)."""
    dur = duracion(video)
    W0, H0 = tamano(video)
    alto = int(round(ancho * H0 / W0 / 2)) * 2
    cuadros = []
    for i in range(n):
        t = dur * (i + 0.5) / n
        out = subprocess.run(
            ["ffmpeg", "-loglevel", "error", "-ss", f"{t:.2f}", "-i", str(video), "-frames:v", "1",
             "-vf", f"scale={ancho}:{alto},format=gray", "-f", "rawvideo", "-"],
            capture_output=True, check=True).stdout
        if len(out) == ancho * alto:
            cuadros.append(np.frombuffer(out, np.uint8).reshape(alto, ancho))
    return np.stack(cuadros).astype(np.float32)


def detectar_logo(video: Path) -> dict | None:
    """Busca en las esquinas una zona que no cambia en todo el video pero tiene bordes (un logo).

    Devuelve {esquina, x, y, w, h} en píxeles del video original, o None.
    """
    cfg = estilo("limpieza")["logo"]
    f = _leer_fotogramas(video, cfg["muestras"])
    _, H, W = f.shape
    var = f.std(axis=0)
    media = f.mean(axis=0)
    gy, gx = np.gradient(media)
    borde = np.hypot(gx, gy)
    # Fijo, con bordes y no negro (las bandas negras también son fijas).
    mascara = (var < cfg["variacion_max"]) & (borde > 8) & (media > 25)
    tw, th = int(W * cfg["tam_rel"]), int(H * cfg["tam_rel"] * 1.3)
    zonas = {"arriba_derecha": (W - tw, 0), "abajo_derecha": (W - tw, H - th),
             "arriba_izquierda": (0, 0), "abajo_izquierda": (0, H - th)}
    mejor, puntos = None, 0
    for nombre in cfg["esquinas"]:
        x0, y0 = zonas[nombre]
        m = mascara[y0:y0 + th, x0:x0 + tw]
        if m.sum() > puntos:
            puntos, mejor = int(m.sum()), (nombre, x0, y0, m)
    if mejor is None or puntos < 40:
        return None
    nombre, x0, y0, m = mejor
    ys, xs = np.nonzero(m)
    x1, x2 = np.percentile(xs, [2, 98]).astype(int)
    y1, y2 = np.percentile(ys, [2, 98]).astype(int)
    Wo, Ho = tamano(video)
    k = Wo / W
    pad = 4
    x, y = max(int((x0 + x1) * k) - pad, 1), max(int((y0 + y1) * k) - pad, 1)
    w = min(int((x2 - x1 + 1) * k) + 2 * pad, Wo - x - 1)
    h = min(int((y2 - y1 + 1) * k) + 2 * pad, Ho - y - 1)
    return {"esquina": nombre, "x": x, "y": y, "w": w, "h": h, "pixeles_fijos": puntos}


def tramos_autopromocion(transcripcion: list[dict]) -> list[dict]:
    """Tramos de la narración que hablan del canal y no de la película."""
    frases = estilo("limpieza")["frases_autopromocion"]
    patron = re.compile("|".join(re.escape(p) for p in frases), re.I)
    tramos = []
    for t in transcripcion:
        hallado = patron.findall(t["texto"])
        if hallado:
            tramos.append({"inicio": t["inicio"], "fin": t["fin"],
                           "motivo": "autopromoción: " + ", ".join(sorted({h.lower() for h in hallado})),
                           "texto": t["texto"]})
    return tramos


def pantalla_final(cortes: list[dict], dur_total: float) -> dict | None:
    """Un plano largo y fijo al final suele ser la despedida del canal."""
    cfg = estilo("limpieza")["pantalla_final"]
    for p in reversed(cortes):
        if p["inicio"] < dur_total - cfg["buscar_ultimos_s"]:
            break
        if p["dur"] >= cfg["plano_estatico_min_s"] and p["fin"] >= dur_total - 1:
            return {"inicio": p["inicio"], "fin": p["fin"], "motivo": "pantalla final fija"}
    return None


def filtro_logo(logo: dict | None) -> str:
    """Filtro de FFmpeg que borra el logo rellenando con los píxeles vecinos."""
    if not logo:
        return "null"
    return f"delogo=x={logo['x']}:y={logo['y']}:w={logo['w']}:h={logo['h']}"


if __name__ == "__main__":
    import sys
    print(json.dumps(detectar_logo(Path(sys.argv[1])), indent=1))
