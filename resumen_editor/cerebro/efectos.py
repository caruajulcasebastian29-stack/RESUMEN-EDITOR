"""Capa · Efectos de imagen que pone el editor en cada toma.

Mide con OpenCV, sin modelos de IA:
  - acercamiento / alejamiento (zoom) y paneo: flujo óptico entre cuadros de la toma
  - blanco y negro: casi sin color
  - tinte: toda la imagen teñida de un color (rojo, azul…)
  - barras negras arriba/abajo (formato cine) o a los lados
  - movimiento dentro de la toma (quieta, normal, agitada) para saber qué tomas eligen para cada momento
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import numpy as np

ANCHO = 320
MUESTRAS = 5


_altos: dict[str, int] = {}


def _alto(video: Path) -> int:
    """Alto de la imagen escalada a ANCHO (par, como lo deja FFmpeg con scale=ANCHO:-2)."""
    if str(video) not in _altos:
        out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
                              "-of", "csv=p=0", str(video)], capture_output=True, text=True).stdout.strip().split(",")
        w, h = int(out[0]), int(out[1])
        _altos[str(video)] = int(round(ANCHO * h / w / 2) * 2)
    return _altos[str(video)]


def _cuadros(video: Path, a: float, b: float) -> np.ndarray:
    dur = max(b - a, 0.1)
    fps = MUESTRAS / dur
    datos = subprocess.run(["ffmpeg", "-loglevel", "error", "-ss", f"{a + 0.04:.3f}", "-t", f"{dur - 0.08:.3f}",
                            "-i", str(video), "-vf", f"fps={fps:.4f},scale={ANCHO}:-2", "-f", "rawvideo",
                            "-pix_fmt", "rgb24", "-"], capture_output=True).stdout
    alto = _alto(video)
    n = len(datos) // (ANCHO * alto * 3)
    if not n:
        return np.zeros((0, alto, ANCHO, 3), np.uint8)
    datos = datos[: n * ANCHO * alto * 3]
    return np.frombuffer(datos, np.uint8).reshape(-1, alto, ANCHO, 3)


def _zoom(c0: np.ndarray, c1: np.ndarray) -> tuple[float, float]:
    """(escala por cuadro, paneo en fracción del ancho) entre dos cuadros."""
    import cv2
    g0, g1 = cv2.cvtColor(c0, cv2.COLOR_RGB2GRAY), cv2.cvtColor(c1, cv2.COLOR_RGB2GRAY)
    f = cv2.calcOpticalFlowFarneback(g0, g1, None, 0.5, 3, 21, 3, 5, 1.1, 0)
    H, W = g0.shape
    ys, xs = np.mgrid[0:H:8, 0:W:8]
    u, v = f[::8, ::8, 0], f[::8, ::8, 1]
    x, y = (xs - W / 2).ravel(), (ys - H / 2).ravel()
    A = np.concatenate([np.stack([x, np.ones_like(x), np.zeros_like(x)], 1),
                        np.stack([y, np.zeros_like(y), np.ones_like(y)], 1)])
    rhs = np.concatenate([u.ravel(), v.ravel()])
    (s, tx, _), *_ = np.linalg.lstsq(A, rhs, rcond=None)
    return float(s), float(tx / W)


def _barras(c: np.ndarray) -> str | None:
    g = c.mean(2)
    filas, cols = g.mean(1), g.mean(0)
    arriba = (filas[: len(filas) // 6] < 12).mean() > 0.8 and (filas[-len(filas) // 6:] < 12).mean() > 0.8
    lados = (cols[: len(cols) // 8] < 12).mean() > 0.8 and (cols[-len(cols) // 8:] < 12).mean() > 0.8
    return "cine" if arriba else ("lados" if lados else None)


def _tinte(c: np.ndarray) -> tuple[bool, str | None]:
    import cv2
    hsv = cv2.cvtColor(c, cv2.COLOR_RGB2HSV)
    sat = hsv[..., 1].astype(float) / 255
    if float(sat.mean()) < 0.06:
        return True, None  # blanco y negro
    colores = hsv[..., 0][sat > 0.25]
    if len(colores) > 0.6 * sat.size:
        tono = float(np.median(colores)) * 2
        variacion = float(np.std(colores)) * 2
        if variacion < 18:
            nombre = ("rojo" if tono < 20 or tono > 330 else "naranja" if tono < 45 else "amarillo" if tono < 70 else
                      "verde" if tono < 170 else "azul" if tono < 260 else "morado")
            return False, nombre
    return False, None


def analizar(video: Path, carpeta: Path, tomas: list[dict], dur: float, aviso=None) -> dict:
    destino = carpeta / "efectos.json"
    parcial = carpeta / "efectos.parcial.json"
    if destino.exists():
        return json.loads(destino.read_text(encoding="utf-8"))
    lista = json.loads(parcial.read_text(encoding="utf-8")) if parcial.exists() else []
    hechas = {x["n"] for x in lista}
    for i, t in enumerate(tomas):
        if t["n"] in hechas:
            continue
        c = _cuadros(video, t["inicio"], t["fin"])
        r = {"n": t["n"], "inicio": t["inicio"], "fin": t["fin"]}
        if len(c) >= 2:
            pasos = [_zoom(c[k], c[k + 1]) for k in range(len(c) - 1)]
            escala = float(np.median([p[0] for p in pasos]))
            paneo = float(np.median([p[1] for p in pasos]))
            dif = float(np.mean([np.abs(c[k + 1].astype(int) - c[k].astype(int)).mean() for k in range(len(c) - 1)]))
            seg = (t["fin"] - t["inicio"]) / max(1, len(c) - 1)
            r["zoom"] = "acerca" if escala / seg > 0.012 else ("aleja" if escala / seg < -0.012 else None)
            r["paneo"] = bool(abs(paneo) / seg > 0.04)
            r["movimiento"] = "quieta" if dif < 4 else ("agitada" if dif > 22 else "normal")
        if len(c):
            medio = c[len(c) // 2]
            bn, r["tinte"] = _tinte(medio)
            r["blanco_negro"] = bool(bn)
            r["barras"] = _barras(medio)
        lista.append(r)
        if i % 25 == 24 or i == len(tomas) - 1:
            parcial.write_text(json.dumps(lista), encoding="utf-8")
            if aviso:
                aviso("Buscando efectos de imagen", 100 * (i + 1) / len(tomas))
    datos = {"tomas": lista, "resumen": resumen(lista)}
    destino.write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")
    parcial.unlink(missing_ok=True)
    return datos


def resumen(lista: list[dict]) -> dict:
    n = len(lista) or 1

    def frac(f):
        return round(sum(1 for x in lista if f(x)) / n, 3)
    tintes: dict[str, int] = {}
    for x in lista:
        if x.get("tinte"):
            tintes[x["tinte"]] = tintes.get(x["tinte"], 0) + 1
    return {"tomas": len(lista),
            "con_acercamiento": frac(lambda x: x.get("zoom") == "acerca"),
            "con_alejamiento": frac(lambda x: x.get("zoom") == "aleja"),
            "con_paneo": frac(lambda x: x.get("paneo")),
            "blanco_y_negro": frac(lambda x: x.get("blanco_negro")),
            "con_tinte": frac(lambda x: x.get("tinte")), "tintes": tintes,
            "barras_cine": frac(lambda x: x.get("barras") == "cine"),
            "movimiento": {m: frac(lambda x, m=m: x.get("movimiento") == m) for m in ("quieta", "normal", "agitada")}}
