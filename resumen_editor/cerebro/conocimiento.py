"""Conocimiento de fábrica: lo que ya se estudió de 8 resúmenes de referencia antes de crear la app.

Viene dentro del instalador (recursos/conocimiento) para que la IA no empiece de cero:
  - guia.md            resumen corto que va en las instrucciones del guionista
  - fichas_base.json   medidas de los 8 videos (cortes, tomas, palabras por minuto, música bajo la voz)
  - notas/*.md         observaciones detalladas de cada video, que se guardan en la memoria para consultarlas
Lo que Jhon le enseña después en «Aprender» se suma a esto; no lo reemplaza.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache

from ..config import CARPETA_RECURSOS

CARPETA = CARPETA_RECURSOS / "conocimiento"
PREFIJO = "base:"


@lru_cache(maxsize=1)
def guia() -> str:
    ruta = CARPETA / "guia.md"
    return ruta.read_text(encoding="utf-8").strip() if ruta.exists() else ""


def fichas_base() -> list[dict]:
    ruta = CARPETA / "fichas_base.json"
    return json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else []


def trozos_notas() -> list[dict]:
    """Cada viñeta o fila de las notas, con el título de su sección y el archivo de origen."""
    salida = []
    for ruta in sorted((CARPETA / "notas").glob("*.md")):
        seccion, cabecera = "", None
        for linea in ruta.read_text(encoding="utf-8").splitlines():
            linea = linea.strip()
            if not linea.startswith("|"):
                cabecera = None
            if linea.startswith("#"):
                seccion = linea.lstrip("# ").strip()
                continue
            if not linea or set(linea) <= set("|-: "):
                continue
            if linea.startswith("|"):
                celdas = [c.strip() for c in linea.strip("|").split("|")]
                if cabecera is None:  # primera fila de la tabla: los nombres de las columnas
                    cabecera = celdas
                    continue
                pares = [f"{cab}: {c}" if cab else c for cab, c in zip(cabecera[1:], celdas[1:]) if c]
                texto = f"{celdas[0]} — " + "; ".join(pares)
            else:
                texto = linea.lstrip("-0123456789. ")
            texto = re.sub(r"[*`]", "", texto).strip()
            if len(texto) >= 25:
                salida.append({"archivo": ruta.stem, "seccion": seccion, "texto": texto[:600]})
    return salida


def sembrar() -> int:
    """Guarda las notas en la memoria una sola vez (si ya están, no hace nada). Necesita Ollama."""
    from . import memoria
    if memoria.hay_video(PREFIJO):
        return 0
    filas = [{"video": PREFIJO + t["archivo"], "inicio": 0.0, "funcion": "nota", "recurso": t["seccion"] or "general",
              "frase": t["texto"], "por_que": f"observado en {t['archivo']}", "tono": ""} for t in trozos_notas()]
    return memoria.guardar_filas(filas)


def manual_texto(manual: dict | None) -> str:
    """Lo aprendido de los videos que Jhon le enseñó, en frases para el guionista."""
    if not manual or not manual.get("videos_propios"):
        return ""
    def med(clave):
        v = manual.get(clave) or {}
        return v.get("mediana")
    lineas = [f"Además, de {manual['videos_propios']} videos que Jhon le enseñó:"]
    if med("palabras_por_minuto"):
        lineas.append(f"- El narrador habla a unas {med('palabras_por_minuto'):.0f} palabras por minuto.")
    if med("tarjetas_tiempo_por_minuto"):
        lineas.append(f"- Ponen tarjetas de tiempo unas {med('tarjetas_tiempo_por_minuto'):.1f} veces por minuto"
                      + (f", por ejemplo: {', '.join(manual.get('ejemplos_tarjetas', [])[:6])}" if manual.get("ejemplos_tarjetas") else "") + ".")
    if manual.get("ejemplos_titulos"):
        lineas.append(f"- Títulos que usaron: {'; '.join(manual['ejemplos_titulos'][:5])}.")
    if manual.get("ejemplos_rotulos"):
        lineas.append(f"- Rótulos de personajes: {', '.join(manual['ejemplos_rotulos'][:8])}.")
    if med("relacion_voz_cortes") is not None:
        r = med("relacion_voz_cortes")
        lineas.append("- Cuando el narrador acelera, el montaje también corta más rápido." if r > 0.3 else
                      "- La velocidad de corte no sigue a la de la voz: el montaje va por su cuenta.")
    if med("gancho_cortes_por_minuto"):
        lineas.append(f"- El gancho va a unos {med('gancho_cortes_por_minuto'):.0f} cortes por minuto.")
    if med("risas_por_minuto"):
        lineas.append(f"- Ponen risas unas {med('risas_por_minuto'):.1f} veces por minuto.")
    if med("efectos_comicos_por_minuto"):
        lineas.append(f"- Efectos de sonido cómicos: unos {med('efectos_comicos_por_minuto'):.1f} por minuto.")
    for x in (manual.get("para_copiar") or [])[-6:]:
        lineas.append(f"- Técnica vista en sus videos: {x}")
    for g in (manual.get("ganchos") or [])[-3:]:
        if isinstance(g, dict) and g.get("frase"):
            lineas.append(f"- Gancho real ({g.get('tipo', '')}): «{g['frase']}»")
    return "\n".join(lineas)
