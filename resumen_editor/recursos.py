"""Recursos visuales y sonoros aprendidos de los videos de referencia.

Tarjetas amarillas de tiempo y lugar (FERDAN), rótulos de personaje (FERDAN / Así Pasó),
sticker de censura (Así Pasó, con nuestro mapache), sonido para la grosería cortada y el
mapache en la esquina (plan B: poses fijas con rebote y movimiento al ritmo de la voz).
"""
from __future__ import annotations

import math
import subprocess
import wave
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .config import CARPETA_RECURSOS, estilo

FUENTE = CARPETA_RECURSOS / "fuentes" / "Anton-Regular.ttf"
MAPACHE = CARPETA_RECURSOS / "mapache"

# Qué pose usa el plan B para cada emoción marcada en el guion.
POSES = {
    "tranquilo": "busto_tranquilo", "burla": "busto_burla", "aburrido": "brazos_cruzados",
    "pensando": "rascandose", "furioso": "busto_burla", "risa": "busto_burla",
    "asco": "brazos_cruzados", "groseria": "busto_burla",
}


def _hex(c: str) -> tuple[int, int, int]:
    c = c.lstrip("#")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


def texto_con_borde(texto: str, alto_letra: int, color: str, borde: str, ancho_max: int) -> Image.Image:
    """Imagen transparente con el texto en mayúsculas, en una o dos líneas, con borde grueso."""
    texto = texto.upper()
    fuente = ImageFont.truetype(str(FUENTE), alto_letra)
    grosor = max(3, alto_letra // 9)
    palabras, lineas, actual = texto.split(), [], ""
    for p in palabras:
        prueba = (actual + " " + p).strip()
        if fuente.getlength(prueba) + 2 * grosor > ancho_max and actual:
            lineas.append(actual)
            actual = p
        else:
            actual = prueba
    lineas.append(actual)
    ancho = int(max(fuente.getlength(l) for l in lineas)) + 4 * grosor
    alto_linea = int(alto_letra * 1.15)
    img = Image.new("RGBA", (ancho, alto_linea * len(lineas) + 4 * grosor), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for i, l in enumerate(lineas):
        x = (ancho - fuente.getlength(l)) / 2
        d.text((x, 2 * grosor + i * alto_linea), l, font=fuente, fill=_hex(color),
               stroke_width=grosor, stroke_fill=_hex(borde))
    return img


def tarjeta(texto: str, tamano: tuple[int, int], tipo: str = "tarjeta_tiempo") -> Image.Image:
    """Lienzo transparente del tamaño del video con la tarjeta centrada (o el rótulo abajo a la izquierda)."""
    cfg = estilo("montaje")[tipo]
    W, H = tamano
    t = texto_con_borde(texto, int(H * cfg["tamano_rel"]), cfg["color"], cfg["borde"], int(W * 0.86))
    lienzo = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    if cfg["posicion"] == "centro":
        pos = ((W - t.width) // 2, (H - t.height) // 2)
    else:  # abajo_izquierda
        pos = (int(W * 0.04), int(H * 0.80) - t.height // 2)
    lienzo.alpha_composite(t, pos)
    return lienzo


def sonido_corte(destino: Path, dur: float | None = None, sr: int = 44100) -> Path:
    """Sonido corto para tapar la grosería: bocina de juguete en dos tonos (propio, sin derechos de nadie)."""
    dur = dur or estilo("montaje")["groseria"]["dur_s"]
    t = np.arange(int(sr * dur)) / sr
    f = np.where(t < dur / 2, 620, 470)
    onda = np.sign(np.sin(2 * np.pi * f * t)) * 0.35 + np.sin(2 * np.pi * f * 2 * t) * 0.15
    env = np.minimum(1, t / 0.01) * np.minimum(1, (dur - t) / 0.03)
    y = (onda * env * 32767 * 0.7).astype(np.int16)
    destino.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(destino), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(y.tobytes())
    return destino


def pose(emocion: str) -> Image.Image:
    nombre = POSES.get(emocion, "busto_tranquilo")
    return Image.open(MAPACHE / f"{nombre}.png").convert("RGBA")


def sticker_censura(alto: int) -> Image.Image:
    """El mapache con cara de burla sirve de sticker para tapar (como el logo con cara de Así Pasó)."""
    p = pose("burla")
    k = alto / p.height
    return p.resize((int(p.width * k), alto), Image.LANCZOS)


def volumen_por_cuadro(audio: Path, fps: int, inicio: float, dur: float) -> np.ndarray:
    """Volumen (0–1) de la voz en cada cuadro, para mover al mapache al ritmo de lo que dice."""
    sr = 16000
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-ss", f"{inicio:.3f}", "-t", f"{dur:.3f}", "-i", str(audio),
                          "-ac", "1", "-ar", str(sr), "-f", "s16le", "-"], capture_output=True, check=True).stdout
    a = np.frombuffer(raw, np.int16).astype(np.float32) / 32768
    n = max(1, int(dur * fps))
    if not len(a):
        return np.zeros(n)
    paso = max(1, len(a) // n)
    v = np.array([np.sqrt(np.mean(a[i * paso:(i + 1) * paso] ** 2)) if a[i * paso:(i + 1) * paso].size else 0.0
                  for i in range(n)])
    return np.clip(v / (v.max() + 1e-6), 0, 1)


def cuadros_mapache(emocion: str, tamano: tuple[int, int], dur: float, fps: int,
                    volumen: np.ndarray | None = None) -> list[Image.Image]:
    """Plan B de animación: entra con rebote, respira, se sacude si grita y sigue el volumen de la voz."""
    cfg = estilo("montaje")["mapache_esquina"]
    W, H = tamano
    base = pose(emocion)
    alto = int(H * cfg["alto_rel"])
    base = base.resize((int(base.width * alto / base.height), alto), Image.LANCZOS)
    margen = int(W * cfg["margen_rel"])
    x0, y0 = W - base.width - margen, H - base.height
    n = max(1, int(dur * fps))
    grita = emocion in ("furioso", "groseria")
    cuadros = []
    for i in range(n):
        t = i / fps
        k = max(0.0, min(1.0, t / 0.35, (dur - t) / 0.25))  # entra en 0,35 s y sale en 0,25 s
        rebote = 1 - (1 - k) ** 3 + 0.12 * math.sin(k * math.pi) * (1 - k)
        dy = int((1 - rebote) * base.height)
        v = float(volumen[min(i, len(volumen) - 1)]) if volumen is not None else 0.0
        escala = 1 + 0.012 * math.sin(2 * math.pi * t / 1.8) + 0.05 * v
        sacudida = int(math.sin(t * 60) * 6 * v) if grita else 0
        im = base.resize((int(base.width * escala), int(base.height * escala)), Image.BILINEAR)
        lienzo = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        lienzo.alpha_composite(im, (max(0, x0 - (im.width - base.width) // 2 + sacudida),
                                    min(H - 1, y0 - (im.height - base.height) + dy)))
        cuadros.append(lienzo)
    return cuadros


def escribir_capa(cuadros: list[Image.Image], fps: int, destino: Path) -> Path:
    """Guarda una secuencia transparente como video con canal alfa (para superponer con FFmpeg)."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    W, H = cuadros[0].size
    p = subprocess.Popen(["ffmpeg", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{W}x{H}",
                          "-r", str(fps), "-i", "-", "-c:v", "qtrle", str(destino)], stdin=subprocess.PIPE)
    for c in cuadros:
        p.stdin.write(c.tobytes())
    p.stdin.close()
    p.wait()
    return destino
