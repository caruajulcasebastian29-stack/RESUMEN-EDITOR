"""Capa 4 · Imagen: el modelo de visión mira cada toma y dice qué es y qué pasa.

Por toma se saca el fotograma central (y uno más si la toma es larga). Tomas casi idénticas a la
anterior reutilizan su descripción, para no gastar tiempo en lo mismo.

De cada toma queda:
  tipo          pelicula · personaje_del_canal · tarjeta_texto · meme_o_inserto · autopromocion ·
                pantalla_negra · otro
  descripcion   una frase en español
  personajes    quiénes se ven (descripción corta, sin inventar nombres)
  emocion       el tono de la imagen
  texto         lo que esté escrito en pantalla
  superpuesto   cosas pegadas encima de la película (personaje del canal, sticker, logo) y dónde
"""
from __future__ import annotations

import json
import subprocess
from enum import Enum
from pathlib import Path

import numpy as np
from pydantic import BaseModel, Field

from . import ia

ANCHO = 448          # ancho del fotograma que se le pasa al modelo
TOMA_LARGA_S = 4.0   # desde aquí se miran dos fotogramas
PARECIDO = 6         # distancia de huella (0-64) por debajo de la cual dos tomas son «la misma»


class Tipo(str, Enum):
    pelicula = "pelicula"
    personaje_del_canal = "personaje_del_canal"
    tarjeta_texto = "tarjeta_texto"
    meme_o_inserto = "meme_o_inserto"
    autopromocion = "autopromocion"
    pantalla_negra = "pantalla_negra"
    otro = "otro"


class Lugar(str, Enum):
    arriba_izquierda = "arriba_izquierda"
    arriba_derecha = "arriba_derecha"
    abajo_izquierda = "abajo_izquierda"
    abajo_derecha = "abajo_derecha"
    centro = "centro"
    pantalla_completa = "pantalla_completa"


class Superpuesto(BaseModel):
    que: str = Field(description="qué es: personaje animado del canal, sticker, logo, flecha, texto…")
    lugar: Lugar


class Toma(BaseModel):
    tipo: Tipo
    descripcion: str = Field(description="una frase en español: qué se ve y qué pasa")
    personajes: list[str] = Field(description="personas o personajes visibles, descritos en pocas palabras")
    emocion: str = Field(description="tono de la imagen en una o dos palabras: tensión, risa, tristeza…")
    texto: str = Field(description="texto escrito en pantalla, vacío si no hay")
    superpuesto: list[Superpuesto] = Field(description="elementos pegados encima de la imagen de la película")


SISTEMA = ("Eres el analista visual de un editor de resúmenes de películas para YouTube. Miras fotogramas "
           "y describes con precisión lo que se ve, sin inventar nombres ni hechos que no estén en la imagen. "
           "Respondes siempre en español.")

PEDIDO = """Fotograma(s) de una toma de un video de resumen de película (segundo {ini:.1f} a {fin:.1f}).

Clasifica la toma:
- pelicula: imagen de la película que se resume
- personaje_del_canal: aparece la mascota o avatar del canal (dibujo o personaje animado que no es de la película)
- tarjeta_texto: pantalla dominada por un texto o rótulo del editor
- meme_o_inserto: fragmento de otra película, serie, meme o video ajeno a la película
- autopromocion: pide suscribirse, anuncia otro canal, redes, patrocinio
- pantalla_negra: negro o casi negro
- otro

Si sobre la imagen de la película hay algo pegado (mascota del canal en una esquina, sticker, logo, flecha),
anótalo en "superpuesto" con su lugar."""


def _fotograma(video: Path, t: float, destino: Path) -> Path:
    if not destino.exists():
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-ss", f"{t:.3f}", "-i", str(video), "-frames:v", "1",
                        "-vf", f"scale={ANCHO}:-2", "-q:v", "3", str(destino)], check=True)
    return destino


def _huella(ruta: Path) -> np.ndarray:
    datos = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(ruta), "-vf", "scale=9:8,format=gray",
                            "-f", "rawvideo", "-"], capture_output=True, check=True).stdout
    g = np.frombuffer(datos, np.uint8).reshape(8, 9).astype(int)
    return (g[:, 1:] > g[:, :-1]).reshape(-1)


def analizar(video: Path, carpeta: Path, tomas: list[dict], aviso=None) -> list[dict]:
    destino = carpeta / "imagen.json"
    hechas: list[dict] = json.loads(destino.read_text(encoding="utf-8")) if destino.exists() else []
    if len(hechas) >= len(tomas):
        return hechas
    fotos = carpeta / "fotogramas"
    fotos.mkdir(exist_ok=True)
    anterior = None
    for i in range(len(hechas), len(tomas)):
        t = tomas[i]
        dur = t["fin"] - t["inicio"]
        medio = _fotograma(video, t["inicio"] + dur / 2, fotos / f"toma_{t['n']:04d}.jpg")
        huella = _huella(medio)
        if anterior is not None and int((huella != anterior[0]).sum()) <= PARECIDO:
            vista = dict(anterior[1], repetida_de=anterior[2])
        else:
            imagenes = [medio]
            if dur >= TOMA_LARGA_S:
                imagenes.insert(0, _fotograma(video, t["inicio"] + dur * 0.2, fotos / f"toma_{t['n']:04d}_a.jpg"))
            r = ia.estructurado(PEDIDO.format(ini=t["inicio"], fin=t["fin"]), Toma, papel="vision",
                                sistema=SISTEMA, imagenes=imagenes, contexto=4096)
            vista = json.loads(r.model_dump_json())
            anterior = (huella, vista, t["n"])
        hechas.append({"n": t["n"], **vista})
        if i % 10 == 9 or i == len(tomas) - 1:
            destino.write_text(json.dumps(hechas, ensure_ascii=False, indent=1), encoding="utf-8")
            if aviso:
                aviso("Mirando cada toma", 100 * (i + 1) / len(tomas))
    ia.liberar("vision")
    return hechas


def resumen(vistas: list[dict], tomas: list[dict]) -> dict:
    """Cuánto tiempo ocupa cada tipo de toma y cómo usa el canal sus elementos propios."""
    dur = {t["n"]: t["fin"] - t["inicio"] for t in tomas}
    total = sum(dur.values()) or 1
    por_tipo: dict[str, float] = {}
    for v in vistas:
        por_tipo[v["tipo"]] = por_tipo.get(v["tipo"], 0) + dur.get(v["n"], 0)
    superpuestos = [(v["n"], s) for v in vistas for s in v.get("superpuesto", [])]
    lugares: dict[str, int] = {}
    for _, s in superpuestos:
        lugares[s["lugar"]] = lugares.get(s["lugar"], 0) + 1
    apariciones = [n for n, s in superpuestos if "personaje" in s["que"].lower() or "mascota" in s["que"].lower()]
    # planos completos del personaje del canal: tramos seguidos de tomas de ese tipo
    tipo_n = {v["n"]: v["tipo"] for v in vistas}
    insertos, actual = [], None
    for t in tomas:
        if tipo_n.get(t["n"]) == "personaje_del_canal":
            actual = [t["inicio"], t["fin"]] if actual is None else [actual[0], t["fin"]]
        elif actual is not None:
            insertos.append(actual)
            actual = None
    if actual is not None:
        insertos.append(actual)
    largo = sorted(b - a for a, b in insertos)
    minutos = max((tomas[-1]["fin"] if tomas else 0) / 60, 1e-6)
    return {"insertos_personaje": {"por_minuto": round(len(insertos) / minutos, 2),
                                   "duracion_mediana_s": round(largo[len(largo) // 2], 2) if largo else None},
            "proporcion_por_tipo": {k: round(v / total, 3) for k, v in por_tipo.items()},
            "superpuestos": len(superpuestos), "lugares_superpuestos": lugares,
            "tomas_con_personaje_del_canal": len(apariciones)}
