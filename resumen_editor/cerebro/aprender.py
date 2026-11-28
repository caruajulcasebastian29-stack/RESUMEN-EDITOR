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

from . import (audio, comprension, conocimiento, efectos, encuadre, imagen, memoria, musica, narracion, palabras,
               ritmo, sonidos, texto_pantalla, tomas, voz)

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

    try:  # la primera vez, las notas de fábrica pasan a la memoria
        conocimiento.sembrar()
    except Exception:
        pass
    dur = _dur(video)
    # primero lo que no usa modelos de lenguaje; al final visión y texto (la tarjeta de 4 GB, de a uno)
    paso("Buscando cortes y transiciones", 1)
    t = tomas.analizar(video, carpeta, dur)
    paso("Separando voz y música", 6)
    au = audio.analizar(video, carpeta)
    paso("Escuchando la música", 14)
    mu = musica.analizar(video, carpeta, t["tomas"], au, dur, aviso=lambda m, p: paso(m, 14 + 0.06 * p))
    paso("Reconociendo sonidos (risas, gritos, golpes, ánimo de la música)", 17)
    so = sonidos.analizar(video, carpeta, t["tomas"], dur, aviso=lambda m, p: paso(m, 17 + 0.03 * p))
    paso("Leyendo el texto en pantalla", 20)
    tx = texto_pantalla.analizar(video, carpeta, t["tomas"], dur, aviso=lambda m, p: paso(m, 20 + 0.12 * p))
    paso("Buscando efectos de imagen", 32)
    ef = efectos.analizar(video, carpeta, t["tomas"], dur, aviso=lambda m, p: paso(m, 32 + 0.08 * p))
    paso("Mirando el encuadre (primeros planos y caras)", 39)
    en = encuadre.analizar(video, carpeta, t["tomas"])
    paso("Transcribiendo y separando hablantes", 40)
    pa = palabras.analizar(carpeta / "voz.wav", carpeta, aviso=lambda m, p: paso(m, 40 + 0.12 * p))
    paso("Midiendo la voz", 52)
    vo = voz.analizar(carpeta / "voz.wav", carpeta, pa)
    ri = ritmo.analizar(t["tomas"], pa, dur)
    paso("Mirando cada toma", 55)
    vi = imagen.analizar(video, carpeta, t["tomas"],
                         aviso=lambda m, p: paso(m, 55 + 0.25 * p))
    paso("Estudiando la narración", 80)
    na = narracion.analizar(carpeta, pa, t["tomas"], vi, au, dur,
                            aviso=lambda m, p: paso(m, 80 + 0.08 * p))
    paso("Describiendo lo que ve, tramo por tramo", 88)
    try:
        from . import estudio
        reglas = estudio._texto_reglas(estudio._reglas())
    except Exception:
        reglas = ""
    co = comprension.analizar(carpeta, video.name, dur, t["tomas"], vi, pa, vo, tx, so, mu, ef, en, reglas,
                              aviso=lambda m, p: paso(m, 88 + 0.08 * p))
    paso("Guardando en la memoria", 96)
    memoria.borrar_video(vid)  # si se reanuda, no duplica
    n = memoria.guardar_video(vid, na)
    n += memoria.guardar_texto_pantalla(vid, tx)
    n += memoria.guardar_filas(comprension.filas_memoria(vid, co))
    ficha = {"video": vid, "archivo": video.name, "duracion": round(dur, 1),
             "tomas": t["resumen"], "audio": {k: v for k, v in au.items() if k != "pausas"} |
             {"pausas": {k: v for k, v in au["pausas"].items() if k != "lista"}},
             "musica": musica.resumen(mu), "texto": tx["resumen"], "efectos": ef["resumen"], "ritmo": ri,
             "sonidos": so["resumen"], "encuadre": en["resumen"], "comprension": co.get("global"),
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


def _ejemplos(fichas, tipo, n=15):
    salida = []
    for f in fichas:
        salida += (f.get("texto") or {}).get(tipo, {}).get("ejemplos", [])
    return list(dict.fromkeys(salida))[:n]


def _moda(fichas, tipo, campo):
    vals = [(f.get("texto") or {}).get(tipo, {}).get(campo) for f in fichas]
    vals = [v for v in vals if v]
    return max(set(vals), key=vals.count) if vals else None


def _proporcion(fichas, *camino):
    vals = []
    for f in fichas:
        v = f
        for c in camino:
            v = v.get(c) if isinstance(v, dict) else None
        if isinstance(v, bool):
            vals.append(v)
    return round(sum(vals) / len(vals), 2) if vals else None


def actualizar_manual() -> dict:
    propias = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(FICHAS.glob("*/ficha.json"))]
    fichas = conocimiento.fichas_base() + propias  # lo estudiado antes de crear la app + lo que Jhon le enseña
    transiciones: dict[str, float] = {}
    for f in fichas:
        total = sum(f["tomas"].get("transiciones", {}).values()) or 1
        for k, v in f["tomas"].get("transiciones", {}).items():
            transiciones[k] = transiciones.get(k, 0) + v / total / len(fichas)
    recursos: dict[str, list[float]] = {}
    for f in fichas:
        for k, v in f["narracion"].get("recursos_por_minuto", {}).items():
            recursos.setdefault(k, []).append(v)
    manual = {
        "videos_estudiados": len(fichas),
        "videos_base": len(fichas) - len(propias),
        "pausas_por_minuto": _rango(_valores(fichas, "narracion", "pausas_por_minuto")),
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
        # capas nuevas (solo salen de los videos que Jhon le enseña)
        "tarjetas_tiempo_por_minuto": _rango(_valores(fichas, "texto", "por_minuto", "tarjeta_tiempo")),
        "rotulos_por_minuto": _rango(_valores(fichas, "texto", "por_minuto", "rotulo")),
        "tiempo_con_subtitulos": _rango(_valores(fichas, "texto", "tiempo_con_subtitulos")),
        "tomas_espejadas": _rango(_valores(fichas, "texto", "tomas_espejadas_aprox")),
        "ejemplos_tarjetas": _ejemplos(propias, "tarjeta_tiempo"),
        "ejemplos_titulos": _ejemplos(propias, "titulo"),
        "ejemplos_rotulos": _ejemplos(propias, "rotulo"),
        "color_tarjetas": _moda(propias, "tarjeta_tiempo", "color"),
        "color_rotulos": _moda(propias, "rotulo", "color"),
        "videos_que_cortan_al_compas": _proporcion(propias, "musica", "corta_al_compas"),
        "cortes_al_pulso": _rango(_valores(fichas, "musica", "cortes_al_pulso")),
        "cambios_musica_por_minuto": _rango(_valores(fichas, "musica", "cambios_por_minuto")),
        "musica_sube_en_pausas_db": _rango(_valores(fichas, "musica", "musica_sube_en_pausas_db")),
        "efectos_sonido_por_minuto": _rango(_valores(fichas, "musica", "efectos_por_minuto")),
        "efectos_sonido_en_corte": _rango(_valores(fichas, "musica", "efectos_en_corte")),
        "lufs_mezcla": _rango(_valores(fichas, "musica", "lufs", "mezcla")),
        "lufs_voz": _rango(_valores(fichas, "musica", "lufs", "voz")),
        "tomas_con_acercamiento": _rango(_valores(fichas, "efectos", "con_acercamiento")),
        "tomas_blanco_y_negro": _rango(_valores(fichas, "efectos", "blanco_y_negro")),
        "tomas_con_tinte": _rango(_valores(fichas, "efectos", "con_tinte")),
        "relacion_voz_cortes": _rango(_valores(fichas, "ritmo", "relacion_voz_cortes")),
        "gancho_cortes_por_minuto": _rango(_valores(fichas, "ritmo", "gancho_cortes_por_minuto")),
        "risas_por_minuto": _rango(_valores(fichas, "sonidos", "por_minuto", "risa")),
        "gritos_por_minuto": _rango(_valores(fichas, "sonidos", "por_minuto", "grito")),
        "efectos_comicos_por_minuto": _rango(_valores(fichas, "sonidos", "por_minuto", "efecto_comico")),
        "golpes_por_minuto": _rango(_valores(fichas, "sonidos", "por_minuto", "golpe")),
        "tomas_primer_plano": _rango([(f.get("encuadre") or {}).get("planos", {}).get("primer_plano", 0) +
                                      (f.get("encuadre") or {}).get("planos", {}).get("primerisimo", 0)
                                      for f in propias if f.get("encuadre")]),
        "para_copiar": [x for f in propias for x in ((f.get("comprension") or {}).get("para_copiar") or [])][-20:],
        "videos_propios": len(propias),
    }
    MANUAL.parent.mkdir(parents=True, exist_ok=True)
    MANUAL.write_text(json.dumps(manual, ensure_ascii=False, indent=1), encoding="utf-8")
    return manual
