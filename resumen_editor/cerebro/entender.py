"""Entender el resumen que entrega la App 1 y diagnosticar lo que falla.

1. Corre las capas de análisis (tomas, separación de audio, palabras, imagen). La narración
   robótica de la App 1 solo sirve aquí, para entender; después se descarta.
2. Arma el mapa de la historia: personajes (con el nombre que usa la narración y cómo se ven),
   y los hechos en orden, cada uno con las tomas que lo muestran.
3. Diagnostica comparando con el manual de estilo aprendido.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import numpy as np
from pydantic import BaseModel, Field

from . import audio, ia, imagen, palabras, tomas
from .imagen import _huella
from .narracion import _lineas

VENTANA_S = 75.0


class Personaje(BaseModel):
    nombre: str = Field(description="nombre tal como lo dice la narración")
    aspecto: str = Field(description="cómo se ve, según las descripciones de las tomas")
    papel: str = Field(description="protagonista, villano, interés amoroso, secundario…")


class Hecho(BaseModel):
    inicio: float
    fin: float
    que_pasa: str = Field(description="lo que ocurre, en una o dos frases claras")
    personajes: list[str]
    emocion: str = Field(description="tensión, risa, tristeza, romance, acción, misterio…")
    importancia: int = Field(ge=1, le=5, description="5 = clave para entender la historia")
    imagen_coincide: bool = Field(description="¿las tomas de ese tramo muestran lo que dice la narración?")


class Tramo(BaseModel):
    personajes: list[Personaje]
    hechos: list[Hecho]


class Pelicula(BaseModel):
    titulo_probable: str = Field(description="título de la película si la narración lo dice o se deduce; si no, vacío")
    genero: str
    premisa: str = Field(description="de qué trata, en dos frases")
    final: str = Field(description="cómo termina, en una frase")


SISTEMA = ("Eres el editor jefe de un canal de resúmenes de películas. Lees la narración de un resumen y la "
           "descripción de sus tomas para entender la historia con exactitud. No inventas nada que no esté en "
           "el material.")

PEDIDO = """Tramo {a:.0f}-{b:.0f} s de un resumen de película.
Narración (cada línea [inicio-fin] texto) y, entre corchetes dobles, lo que muestran las tomas:

{lineas}

Personajes ya conocidos: {conocidos}

Divide el tramo en hechos (cada cambio de situación es un hecho nuevo) y lista los personajes que aparecen."""

PEDIDO_PELI = """Estos son los hechos de un resumen de película, en orden:

{hechos}

Personajes: {personajes}

Resume la película."""


def _dur(video: Path) -> float:
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                 str(video)], capture_output=True, text=True).stdout.strip())


def mapa(carpeta: Path, pal: dict, ts: list[dict], vistas: list[dict], dur: float, aviso=None) -> dict:
    destino = carpeta / "mapa.json"
    m = json.loads(destino.read_text(encoding="utf-8")) if destino.exists() else {"tramos": []}
    if m.get("completo"):
        return m
    por_n = {v["n"]: v for v in vistas}
    personajes: dict[str, dict] = {p["nombre"].lower(): p for t in m["tramos"] for p in t["personajes"]}
    a = len(m["tramos"]) * VENTANA_S
    while a < dur:
        b = min(dur, a + VENTANA_S)
        lineas = _lineas(pal["tramos"], por_n, ts, a, b)
        if lineas:
            conocidos = "; ".join(f"{p['nombre']} ({p['aspecto']})" for p in personajes.values()) or "ninguno"
            r = ia.estructurado(PEDIDO.format(a=a, b=b, lineas=lineas, conocidos=conocidos), Tramo,
                                papel="escritor", sistema=SISTEMA, contexto=12288)
            t = json.loads(r.model_dump_json())
            for p in t["personajes"]:
                personajes.setdefault(p["nombre"].lower(), p)
        else:
            t = {"personajes": [], "hechos": []}
        m["tramos"].append({"desde": a, "hasta": b, **t})
        destino.write_text(json.dumps(m, ensure_ascii=False, indent=1), encoding="utf-8")
        if aviso:
            aviso("Entendiendo la historia", 100 * b / dur)
        a = b
    hechos = []
    for t in m["tramos"]:
        for h in t["hechos"]:
            h["tomas"] = [x["n"] for x in ts if x["inicio"] < h["fin"] and x["fin"] > h["inicio"]]
            hechos.append(h)
    hechos.sort(key=lambda h: h["inicio"])
    for i, h in enumerate(hechos):
        h["id"] = i + 1
    m["hechos"] = hechos
    m["personajes"] = list(personajes.values())
    lista = "\n".join(f"{h['id']}. [{h['inicio']:.0f}s] {h['que_pasa']}" for h in hechos)
    peli = ia.estructurado(PEDIDO_PELI.format(hechos=lista, personajes=", ".join(personajes) or "—"), Pelicula,
                           papel="escritor", sistema=SISTEMA, contexto=16384)
    m["pelicula"] = json.loads(peli.model_dump_json())
    m["completo"] = True
    destino.write_text(json.dumps(m, ensure_ascii=False, indent=1), encoding="utf-8")
    ia.liberar("escritor")
    return m


def diagnosticar(carpeta: Path, ts: dict, vistas: list[dict], m: dict, manual: dict) -> dict:
    """Problemas concretos, cada uno con su ubicación, para que el guion y el montaje los corrijan."""
    problemas = []
    lista = ts["tomas"]
    tope = (manual.get("duracion_toma_max") or {}).get("max") or 3.0
    for t in lista:
        d = t["fin"] - t["inicio"]
        if d > tope * 1.5:
            problemas.append({"tipo": "toma_larga", "inicio": t["inicio"], "fin": t["fin"],
                              "detalle": f"toma de {d:.1f} s; las referencias no pasan de {tope:.1f} s"})
    por_n = {v["n"]: v for v in vistas}
    for t in lista:
        v = por_n.get(t["n"])
        if v and v["tipo"] == "pantalla_negra" and t["fin"] - t["inicio"] > 0.5:
            problemas.append({"tipo": "negro", "inicio": t["inicio"], "fin": t["fin"], "detalle": "pantalla negra"})
    fotos = carpeta / "fotogramas"
    vistos: list[tuple[int, np.ndarray]] = []
    for t in lista:
        f = fotos / f"toma_{t['n']:04d}.jpg"
        if not f.exists():
            continue
        h = _huella(f)
        for n2, h2 in vistos:
            if t["n"] - n2 > 3 and int((h != h2).sum()) <= 4:
                problemas.append({"tipo": "toma_repetida", "inicio": t["inicio"], "fin": t["fin"],
                                  "detalle": f"misma imagen que la toma {n2}"})
                break
        vistos.append((t["n"], h))
    for h in m.get("hechos", []):
        if not h["imagen_coincide"]:
            problemas.append({"tipo": "imagen_no_coincide", "inicio": h["inicio"], "fin": h["fin"],
                              "detalle": h["que_pasa"]})
    cpm = ts["resumen"]["cortes_por_minuto"]
    ref = (manual.get("cortes_por_minuto") or {}).get("mediana")
    ritmo = {"actual": cpm, "referencia": ref, "lento": bool(ref and cpm < ref * 0.75)}
    cuenta: dict[str, int] = {}
    for p in problemas:
        cuenta[p["tipo"]] = cuenta.get(p["tipo"], 0) + 1
    datos = {"problemas": problemas, "ritmo": ritmo, "cuenta": cuenta}
    (carpeta / "diagnostico.json").write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")
    return datos


def entender(video: Path, carpeta: Path, manual: dict, aviso=None) -> dict:
    carpeta.mkdir(parents=True, exist_ok=True)

    def paso(nombre, frac):
        if aviso:
            aviso(nombre, frac)

    dur = _dur(video)
    paso("Buscando cortes", 2)
    ts = tomas.analizar(video, carpeta, dur)
    paso("Separando la narración de la música", 10)
    au = audio.analizar(video, carpeta)
    paso("Transcribiendo la narración", 25)
    pal = palabras.analizar(carpeta / "voz.wav", carpeta)
    paso("Mirando cada toma", 40)
    vistas = imagen.analizar(video, carpeta, ts["tomas"], aviso=lambda mm, p: paso(mm, 40 + 0.3 * p))
    paso("Entendiendo la historia", 70)
    m = mapa(carpeta, pal, ts["tomas"], vistas, dur, aviso=lambda mm, p: paso(mm, 70 + 0.25 * p))
    paso("Buscando fallas", 96)
    diag = diagnosticar(carpeta, ts, vistas, m, manual)
    return {"duracion": dur, "tomas": ts, "audio": au, "palabras": pal, "vistas": vistas, "mapa": m,
            "diagnostico": diag}
