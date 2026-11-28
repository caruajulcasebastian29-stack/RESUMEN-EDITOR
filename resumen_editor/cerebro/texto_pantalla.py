"""Capa · Texto en pantalla: lee lo que el editor escribió sobre la imagen.

Con RapidOCR (gratis, sin internet) se lee el texto de cada toma y se clasifica:
  - tarjeta_tiempo   «MÁS TARDE», «AL DÍA SIGUIENTE»… (centro, letras grandes)
  - titulo           letras grandes al principio del video
  - rotulo           nombre de un personaje (una o dos palabras, aparece una vez)
  - subtitulo        abajo al centro, cambia seguido
  - marca            el mismo texto fijo en la misma esquina en muchas tomas (logo / marca de agua)
  - texto            el resto (frases en jerga, datos, carteles)
De cada uno guarda qué dice, dónde, cuánto dura, de qué color y de qué tamaño. Además estima cuántas tomas
están espejadas (volteadas): el texto volteado no se puede leer, pero al voltearlo de nuevo sí.
"""
from __future__ import annotations

import json
import re
import subprocess
from collections import Counter
from pathlib import Path

import numpy as np

ANCHO = 960
TIEMPO = re.compile(r"\b(m[aá]s tarde|despu[eé]s|luego|al d[ií]a siguiente|a la ma[ñn]ana|esa noche|d[ií]as|semanas|"
                    r"meses|a[ñn]os|horas|minutos|momentos|mientras tanto|en ese momento|a continuaci[oó]n|"
                    r"tiempo despu[eé]s|al otro d[ií]a)\b", re.I)
_ocr = None


def _motor():
    global _ocr
    if _ocr is None:
        try:
            from rapidocr_onnxruntime import RapidOCR
        except ImportError as e:
            raise RuntimeError("El lector de texto en pantalla se está instalando todavía. Espera unos minutos "
                               "y pulsa «Reanudar»: seguirá desde donde quedó.") from e
        _ocr = RapidOCR()
    return _ocr


def _cuadro(video: Path, t: float) -> np.ndarray:
    datos = subprocess.run(["ffmpeg", "-loglevel", "error", "-ss", f"{t:.3f}", "-i", str(video), "-frames:v", "1",
                            "-vf", f"scale={ANCHO}:-2", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                           capture_output=True, check=True).stdout
    alto = len(datos) // (ANCHO * 3)
    return np.frombuffer(datos[: alto * ANCHO * 3], np.uint8).reshape(alto, ANCHO, 3)


def _leer(img: np.ndarray, minimo: float = 0.6) -> list[dict]:
    if img.ndim != 3 or img.shape[0] < 16:  # cuadro vacío (por ejemplo, pasado el final del video)
        return []
    r, _ = _motor()(img)
    salida = []
    H, W = img.shape[:2]
    for caja, texto, puntaje in r or []:
        puntaje = float(puntaje)
        texto = texto.strip()
        if puntaje < minimo or len(re.sub(r"\W", "", texto)) < 2:
            continue
        xs, ys = [p[0] for p in caja], [p[1] for p in caja]
        x0, x1, y0, y1 = max(0, min(xs)), min(W, max(xs)), max(0, min(ys)), min(H, max(ys))
        salida.append({"texto": texto, "puntaje": round(puntaje, 2), "x": (x0 + x1) / 2 / W, "y": (y0 + y1) / 2 / H,
                       "alto": (y1 - y0) / H, "ancho": (x1 - x0) / W, "color": _color(img, x0, x1, y0, y1),
                       "contorno": _contorno(img, x0, x1, y0, y1)})
    return salida


def _color(img, x0, x1, y0, y1) -> str:
    """Color de las letras: el tono más brillante dentro de la caja."""
    zona = img[int(y0):int(y1), int(x0):int(x1)].reshape(-1, 3).astype(float)
    if not len(zona):
        return "?"
    brillo = zona.mean(1)
    letras = zona[brillo >= np.percentile(brillo, 80)]
    r, g, b = letras.mean(0)
    if max(r, g, b) - min(r, g, b) < 30:
        return "blanco" if r > 170 else ("gris" if r > 90 else "negro")
    if r > 180 and g > 150 and b < 110:
        return "amarillo"
    if r > 160 and g < 110:
        return "rojo"
    if g > r and g > b:
        return "verde"
    if b > r:
        return "azul"
    return "naranja" if r > g else "otro"


def _contorno(img, x0, x1, y0, y1) -> float:
    """Las letras que pone el editor tienen borde oscuro grueso alrededor de un relleno claro:
    se mide cuánto hay a la vez de muy claro y de muy oscuro dentro de la caja (0 a 1)."""
    zona = img[int(y0):int(y1), int(x0):int(x1)].mean(2) if y1 > y0 and x1 > x0 else np.zeros(1)
    if zona.size < 20:
        return 0.0
    claro, oscuro = (zona > 190).mean(), (zona < 45).mean()
    return round(float(min(claro, oscuro) * 4), 2)


def _es_basura(texto: str) -> bool:
    """Lecturas sueltas de carteles de la película: letras y números mezclados, pocas letras."""
    for p in texto.split():
        if re.search(r"[a-záéíóúñ]", p, re.I) and re.search(r"\d", p) and not re.fullmatch(r"\d+[a-z]{1,3}", p, re.I):
            return True
    letras = len(re.findall(r"[a-záéíóúñ]", texto, re.I))
    return letras < 3


def _del_editor(x: dict) -> bool:
    """¿Lo puso el editor o es un cartel que ya estaba en la película?"""
    if _es_basura(x["texto"]):
        return False
    if TIEMPO.search(x["texto"]):
        return x["puntaje"] >= 0.7
    return x["puntaje"] >= 0.9 or (x["puntaje"] >= 0.75 and x.get("contorno", 0) >= 0.25)


def _lugar(x: float, y: float) -> str:
    v = "arriba" if y < 0.33 else ("abajo" if y > 0.7 else "centro")
    h = "izquierda" if x < 0.33 else ("derecha" if x > 0.67 else "")
    return f"{v}_{h}" if h else v


def analizar(video: Path, carpeta: Path, tomas: list[dict], dur: float, aviso=None) -> dict:
    destino = carpeta / "texto.json"
    parcial = carpeta / "texto.parcial.json"
    if destino.exists():
        return json.loads(destino.read_text(encoding="utf-8"))
    hecho = json.loads(parcial.read_text(encoding="utf-8")) if parcial.exists() else {"lecturas": [], "espejo": [0, 0]}
    lecturas, espejo = hecho["lecturas"], hecho["espejo"]
    vistas = {x["n"] for x in lecturas}
    sin_texto = 0
    for i, t in enumerate(tomas):
        if t["n"] in vistas:
            continue
        d = t["fin"] - t["inicio"]
        momentos = [t["inicio"] + d / 2] if d < 2.5 else [t["inicio"] + 0.4, t["inicio"] + d * 0.7]
        textos = []
        for m in momentos:
            img = _cuadro(video, m)
            leidos = _leer(img)
            textos += leidos
            if not leidos:
                sin_texto += 1
                if sin_texto % 3 == 1:  # una de cada tres tomas sin texto: ¿está volteada?
                    espejo[0] += 1
                    if any(x["puntaje"] > 0.8 and len(x["texto"]) >= 4 for x in _leer(img[:, ::-1].copy(), 0.8)):
                        espejo[1] += 1
        lecturas.append({"n": t["n"], "inicio": t["inicio"], "fin": t["fin"], "textos": textos})
        if i % 20 == 19 or i == len(tomas) - 1:
            parcial.write_text(json.dumps(hecho, ensure_ascii=False), encoding="utf-8")
            if aviso:
                aviso("Leyendo el texto en pantalla", 100 * (i + 1) / len(tomas))
    datos = {"elementos": _agrupar(lecturas), "tomas_revisadas_espejo": espejo[0], "tomas_espejadas": espejo[1]}
    datos["resumen"] = resumen(datos, dur)
    destino.write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")
    parcial.unlink(missing_ok=True)
    return datos


def _clave(texto: str) -> str:
    return re.sub(r"\W+", " ", texto.lower()).strip()


def _agrupar(lecturas: list[dict]) -> list[dict]:
    """Une el mismo texto en tomas seguidas y le pone tipo."""
    total = len(lecturas) or 1
    lecturas = [dict(l, textos=[x for x in l["textos"] if _del_editor(x)]) for l in lecturas]
    por_clave_lugar = Counter((_clave(x["texto"]), _lugar(x["x"], x["y"])) for l in lecturas for x in l["textos"])
    marcas = {k for k, n in por_clave_lugar.items() if n >= max(8, total * 0.25) and k[1] != "centro"}
    elementos: list[dict] = []
    abiertos: dict[tuple, dict] = {}
    for l in lecturas:
        vistos = set()
        for x in l["textos"]:
            k = (_clave(x["texto"]), _lugar(x["x"], x["y"]))
            vistos.add(k)
            if k in abiertos and l["inicio"] - abiertos[k]["fin"] < 0.6:
                abiertos[k]["fin"] = l["fin"]
            else:
                abiertos[k] = {"texto": x["texto"], "lugar": k[1], "inicio": l["inicio"], "fin": l["fin"],
                               "color": x["color"], "alto": round(x["alto"], 3), "marca": k in marcas}
                elementos.append(abiertos[k])
        for k in [k for k in abiertos if k not in vistos]:
            abiertos.pop(k)
    apariciones = Counter(_clave(e["texto"]) for e in elementos)
    for e in elementos:
        palabras = len(e["texto"].split())
        lateral = "izquierda" in e["lugar"] or "derecha" in e["lugar"]
        if e["marca"]:
            e["tipo"] = "marca"
        elif TIEMPO.search(e["texto"]) and e["lugar"] == "centro":
            e["tipo"] = "tarjeta_tiempo"
        elif e["inicio"] < 90 and e["alto"] > 0.08 and e["lugar"] == "centro":
            e["tipo"] = "titulo"
        elif e["lugar"] == "abajo" and palabras >= 2 and not lateral:
            e["tipo"] = "subtitulo"
        elif palabras <= 3 and apariciones[_clave(e["texto"])] <= 2 and e["texto"].upper() == e["texto"]:
            e["tipo"] = "rotulo"
        else:
            e["tipo"] = "texto"
        e["dur"] = round(e["fin"] - e["inicio"], 2)
        e.pop("marca")
    return elementos


def resumen(datos: dict, dur: float) -> dict:
    els = datos["elementos"]
    minutos = max(dur / 60, 0.1)
    por_tipo: dict[str, list[dict]] = {}
    for e in els:
        por_tipo.setdefault(e["tipo"], []).append(e)
    salida: dict = {"por_minuto": {t: round(len(v) / minutos, 2) for t, v in por_tipo.items() if t != "marca"}}
    for t, v in por_tipo.items():
        if t == "marca":
            salida["marca_de_agua"] = sorted({f"{e['texto']} ({e['lugar']})" for e in v})[:3]
            continue
        salida[t] = {"cantidad": len(v),
                     "duracion_mediana_s": round(float(np.median([e["dur"] for e in v])), 2),
                     "color": Counter(e["color"] for e in v).most_common(1)[0][0],
                     "lugar": Counter(e["lugar"] for e in v).most_common(1)[0][0],
                     "tamano_rel": round(float(np.median([e["alto"] for e in v])), 3),
                     "ejemplos": list(dict.fromkeys(e["texto"] for e in v))[:12]}
    sub = por_tipo.get("subtitulo", [])
    salida["tiempo_con_subtitulos"] = round(sum(e["dur"] for e in sub) / max(dur, 1), 2)
    rev = datos.get("tomas_revisadas_espejo") or 0
    salida["tomas_espejadas_aprox"] = round(datos.get("tomas_espejadas", 0) / rev, 2) if rev else None
    return salida
