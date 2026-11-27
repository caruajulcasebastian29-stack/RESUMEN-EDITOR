"""Aprender de un video de referencia: corre las seis capas, guarda su ficha y actualiza el manual.

Orden pensado para la tarjeta de 4 GB: primero todo lo que no usa modelos de lenguaje (tomas,
audio, palabras, voz), luego el modelo de visión y al final el de texto, uno por vez.
Cada capa guarda su resultado: si se corta la luz, al volver sigue donde quedó.
"""
from __future__ import annotations

import json
import os
import re
import statistics as st
import subprocess
from pathlib import Path

from . import audio, imagen, memoria, narracion, palabras, tomas, voz

DATOS = Path(os.environ.get("RESUMEN_EDITOR_DATOS", Path.home() / "Documents" / "Resumen Editor"))
FICHAS = DATOS / "referencias"
MANUAL = DATOS / "manual_estilo.json"


def _dur(video: Path) -> float:
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                 str(video)], capture_output=True, text=True).stdout.strip())


def ident(video: Path) -> str:
    return re.sub(r"[^a-z0-9]+", "-", video.stem.lower()).strip("-")[:60]


def aprender(video: Path, aviso=None) -> dict:
    vid = ident(video)
    carpeta = FICHAS / vid
    carpeta.mkdir(parents=True, exist_ok=True)
    final = carpeta / "ficha.json"
    if final.exists():
        return json.loads(final.read_text(encoding="utf-8"))

    def paso(nombre, frac):
        if aviso:
            aviso(nombre, frac)

    dur = _dur(video)
    paso("Buscando cortes y transiciones", 2)
    t = tomas.analizar(video, carpeta, dur)
    paso("Separando voz y música", 12)
    au = audio.analizar(video, carpeta)
    paso("Transcribiendo y separando hablantes", 30)
    pa = palabras.analizar(carpeta / "voz.wav", carpeta)
    paso("Midiendo la voz", 45)
    vo = voz.analizar(carpeta / "voz.wav", carpeta, pa)
    paso("Mirando cada toma", 50)
    vi = imagen.analizar(video, carpeta, t["tomas"],
                         aviso=lambda m, p: paso(m, 50 + 0.3 * p))
    paso("Estudiando la narración", 80)
    na = narracion.analizar(carpeta, pa, t["tomas"], vi, au, dur,
                            aviso=lambda m, p: paso(m, 80 + 0.15 * p))
    paso("Guardando en la memoria", 96)
    n = memoria.guardar_video(vid, na)
    ficha = {"video": vid, "archivo": video.name, "duracion": round(dur, 1),
             "tomas": t["resumen"], "audio": {k: v for k, v in au.items() if k != "pausas"} |
             {"pausas": {k: v for k, v in au["pausas"].items() if k != "lista"}},
             "imagen": imagen.resumen(vi, t["tomas"]), "voz": vo["resumen"],
             "narracion": na["resumen"], "gancho": na.get("gancho"), "ejemplos_en_memoria": n}
    final.write_text(json.dumps(ficha, ensure_ascii=False, indent=1), encoding="utf-8")
    actualizar_manual()
    paso("Listo", 100)
    return ficha


def _valores(fichas, *camino):
    salida = []
    for f in fichas:
        v = f
        for c in camino:
            v = v.get(c) if isinstance(v, dict) else None
            if v is None:
                break
        if isinstance(v, (int, float)):
            salida.append(float(v))
    return salida


def _rango(vals):
    if not vals:
        return None
    return {"mediana": round(st.median(vals), 2), "min": round(min(vals), 2), "max": round(max(vals), 2),
            "videos": len(vals)}


def actualizar_manual() -> dict:
    fichas = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(FICHAS.glob("*/ficha.json"))]
    transiciones: dict[str, float] = {}
    for f in fichas:
        total = sum(f["tomas"]["transiciones"].values()) or 1
        for k, v in f["tomas"]["transiciones"].items():
            transiciones[k] = transiciones.get(k, 0) + v / total / len(fichas)
    recursos: dict[str, list[float]] = {}
    for f in fichas:
        for k, v in f["narracion"]["recursos_por_minuto"].items():
            recursos.setdefault(k, []).append(v)
    manual = {
        "videos_estudiados": len(fichas),
        "cortes_por_minuto": _rango(_valores(fichas, "tomas", "cortes_por_minuto")),
        "duracion_toma_mediana": _rango(_valores(fichas, "tomas", "duracion_toma", "mediana")),
        "duracion_toma_max": _rango(_valores(fichas, "tomas", "duracion_toma", "p90")),
        "transiciones": {k: round(v, 3) for k, v in transiciones.items()},
        "musica_bajo_voz_db": _rango(_valores(fichas, "audio", "musica_bajo_voz_db")),
        "musica_presente": _rango(_valores(fichas, "audio", "musica_presente")),
        "palabras_por_minuto": _rango(_valores(fichas, "narracion", "palabras_por_minuto")),
        "chistes_por_minuto": _rango(_valores(fichas, "narracion", "chistes_por_minuto")),
        "recursos_por_minuto": {k: round(st.median(v), 2) for k, v in recursos.items()},
        "cortes_en_pausas": _rango(_valores(fichas, "narracion", "cortes_en_pausas")),
        "voz_rango_st": _rango(_valores(fichas, "voz", "rango_st_mediana")),
        "voz_palabras_s": _rango(_valores(fichas, "voz", "palabras_s")),
        "personaje_del_canal_tomas": _rango(_valores(fichas, "imagen", "tomas_con_personaje_del_canal")),
        "insertos_personaje_por_minuto": _rango(_valores(fichas, "imagen", "insertos_personaje", "por_minuto")),
        "insertos_personaje_duracion_s": _rango(_valores(fichas, "imagen", "insertos_personaje", "duracion_mediana_s")),
        "ganchos": [f["gancho"] for f in fichas if f.get("gancho")],
    }
    MANUAL.parent.mkdir(parents=True, exist_ok=True)
    MANUAL.write_text(json.dumps(manual, ensure_ascii=False, indent=1), encoding="utf-8")
    return manual
