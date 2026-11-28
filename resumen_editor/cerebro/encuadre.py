"""Capa · Encuadre: cuántas caras hay y qué tan cerca está la cámara en cada toma.

Usa el detector de caras YuNet de OpenCV (gratuito, 230 KB, corre en el procesador). Con el alto de
la cara más grande respecto al alto del cuadro se clasifica la toma:
  primerisimo  la cara llena la pantalla (reacción, momento de emoción)
  primer_plano cara y hombros
  plano_medio  de la cintura para arriba
  general      se ve el lugar; la gente es pequeña
  sin_caras    paisaje, objeto, texto, o un animal
Sirve para saber, por ejemplo, si el editor usa primeros planos en los remates o en los momentos tristes.
"""
from __future__ import annotations

import json
from collections import Counter
from functools import lru_cache
from pathlib import Path

import numpy as np

from . import modelos

ANCHO = 640


@lru_cache(maxsize=1)
def _detector():
    import cv2
    return cv2.FaceDetectorYN.create(str(modelos.ruta("caras")), "", (ANCHO, 360), 0.7, 0.3, 50)


def _plano(alto_rel: float) -> str:
    if alto_rel >= 0.45:
        return "primerisimo"
    if alto_rel >= 0.25:
        return "primer_plano"
    if alto_rel >= 0.11:
        return "plano_medio"
    return "general"


def mirar(img: np.ndarray) -> dict:
    import cv2
    h, w = img.shape[:2]
    if h < 16 or w < 16:
        return {"caras": 0, "plano": "sin_caras", "alto": 0.0}
    escala = ANCHO / w
    chico = cv2.resize(img, (ANCHO, max(16, int(h * escala))))
    det = _detector()
    det.setInputSize((chico.shape[1], chico.shape[0]))
    _, caras = det.detect(chico)
    if caras is None or len(caras) == 0:
        return {"caras": 0, "plano": "sin_caras", "alto": 0.0}
    alto = float(max(c[3] for c in caras)) / chico.shape[0]
    return {"caras": int(len(caras)), "plano": _plano(alto), "alto": round(alto, 3)}


def analizar(video: Path, carpeta: Path, tomas: list[dict], aviso=None) -> dict:
    import cv2
    destino = carpeta / "encuadre.json"
    if destino.exists():
        return json.loads(destino.read_text(encoding="utf-8"))
    cap = cv2.VideoCapture(str(video))
    filas = []
    for i, t in enumerate(tomas):
        medio = t["inicio"] + 0.5 * (t["fin"] - t["inicio"])
        cap.set(cv2.CAP_PROP_POS_MSEC, medio * 1000)
        ok, img = cap.read()
        filas.append({"n": t["n"], **(mirar(img) if ok and img is not None else
                                       {"caras": 0, "plano": "sin_caras", "alto": 0.0})})
        if aviso and i % 40 == 0:
            aviso("Mirando el encuadre", 100 * i / max(1, len(tomas)))
    cap.release()
    datos = {"tomas": filas, "resumen": resumen(filas)}
    destino.write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")
    return datos


def resumen(filas: list[dict]) -> dict:
    n = max(1, len(filas))
    c = Counter(f["plano"] for f in filas)
    return {"planos": {k: round(v / n, 3) for k, v in c.most_common()},
            "tomas_con_varias_caras": round(sum(f["caras"] >= 2 for f in filas) / n, 3)}
