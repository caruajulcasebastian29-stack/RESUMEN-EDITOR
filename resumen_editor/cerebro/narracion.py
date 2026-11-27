"""Capa 5 · Narración: cómo cuenta el canal la historia.

El modelo de texto lee la narración por ventanas de ~90 s, junto con lo que se ve en pantalla en
ese momento, y marca cada recurso: gancho, chiste, apodo, exageración, groserías, eufemismos,
pausas dramáticas, cambios de tono, cierre. De cada recurso queda la frase exacta y por qué funciona,
para que la memoria pueda dar ejemplos reales al escribir guiones nuevos.

Además se mide (sin IA) si los cortes de imagen caen en las pausas de la voz.
"""
from __future__ import annotations

import json
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field

from . import ia

VENTANA_S = 90.0


class Funcion(str, Enum):
    gancho = "gancho"
    presentacion = "presentacion"
    trama = "trama"
    chiste = "chiste"
    reaccion = "reaccion"
    tension = "tension"
    transicion = "transicion"
    cierre = "cierre"
    autopromocion = "autopromocion"


class Recurso(str, Enum):
    apodo = "apodo"
    exageracion = "exageracion"
    comparacion = "comparacion"
    pregunta = "pregunta_al_espectador"
    ironia = "ironia"
    groseria = "groseria"
    eufemismo = "eufemismo"
    referencia = "referencia_cultural"
    anticipacion = "anticipacion"
    juicio = "juicio_moral"
    ninguno = "ninguno"


class Momento(BaseModel):
    inicio: float
    fin: float
    funcion: Funcion
    recurso: Recurso
    frase: str = Field(description="la frase exacta del narrador, copiada tal cual")
    por_que_funciona: str = Field(description="en una frase: qué efecto busca en el espectador")


class Ventana(BaseModel):
    momentos: list[Momento]
    tono: str = Field(description="tono general de la narración en esta ventana, en pocas palabras")
    apodos: list[str] = Field(description="apodos que el narrador pone a personajes, tal como los dice")


class Gancho(BaseModel):
    tipo: str = Field(description="cómo engancha: pregunta, promesa, adelanto del final, chiste, dato curioso…")
    promesa: str = Field(description="qué le promete al espectador si se queda")
    frase: str = Field(description="la frase del gancho copiada tal cual")
    segundos_hasta_la_historia: float = Field(description="segundo en que empieza a contarse la película")


SISTEMA = ("Eres un guionista experto en resúmenes de películas para YouTube en español latino. Analizas la "
           "narración de otros canales para aprender su oficio: cómo enganchan, cómo meten humor y cómo mantienen "
           "la atención. Copias las frases exactas, nunca las inventas.")

PEDIDO = """Narración de un resumen de película entre los segundos {a:.0f} y {b:.0f}.
Cada línea: [inicio-fin] texto. Entre corchetes dobles, lo que se ve en pantalla.

{lineas}

Marca los momentos donde el narrador usa un recurso (chiste, apodo, exageración, groseria, eufemismo,
pregunta al espectador, ironía, anticipación, juicio moral…) o cambia de función (gancho, tensión, cierre).
No marques las frases que solo cuentan la trama sin ningún recurso."""

PEDIDO_GANCHO = """Primeros segundos de un resumen de película:

{lineas}

Describe el gancho: cómo intenta que el espectador no se vaya."""


def _lineas(tramos: list[dict], vistas: dict[int, dict], tomas: list[dict], a: float, b: float) -> str:
    salida = []
    for t in tramos:
        if t["fin"] <= a or t["inicio"] >= b or t["hablante"] != "narrador":
            continue
        se_ve = [vistas[x["n"]]["descripcion"] for x in tomas
                 if x["n"] in vistas and x["inicio"] < t["fin"] and x["fin"] > t["inicio"]]
        vista = f"  [[{' / '.join(dict.fromkeys(se_ve))[:240]}]]" if se_ve else ""
        salida.append(f"[{t['inicio']:.1f}-{t['fin']:.1f}] {t['texto']}{vista}")
    return "\n".join(salida)


def cortes_en_pausas(tomas: list[dict], pausas: list[list[float]], tolerancia: float = 0.25) -> float:
    """Qué parte de los cortes cae en una pausa de la voz (o muy cerca)."""
    if len(tomas) < 2:
        return 0.0
    dentro = 0
    for t in tomas[1:]:
        c = t["inicio"]
        if any(p[0] - tolerancia <= c <= p[1] + tolerancia for p in pausas):
            dentro += 1
    return round(dentro / (len(tomas) - 1), 2)


def analizar(carpeta: Path, palabras: dict, tomas: list[dict], vistas: list[dict], audio: dict,
             dur: float, aviso=None) -> dict:
    destino = carpeta / "narracion.json"
    previo = json.loads(destino.read_text(encoding="utf-8")) if destino.exists() else {"ventanas": []}
    if previo.get("completo"):
        return previo
    por_n = {v["n"]: v for v in vistas}
    tramos = palabras["tramos"]
    if "gancho" not in previo:
        lineas = _lineas(tramos, por_n, tomas, 0, 60)
        previo["gancho"] = json.loads(ia.estructurado(PEDIDO_GANCHO.format(lineas=lineas), Gancho,
                                                      papel="rapido", sistema=SISTEMA).model_dump_json())
    ventanas = previo["ventanas"]
    a = len(ventanas) * VENTANA_S
    while a < dur:
        b = min(dur, a + VENTANA_S)
        lineas = _lineas(tramos, por_n, tomas, a, b)
        if lineas:
            r = ia.estructurado(PEDIDO.format(a=a, b=b, lineas=lineas), Ventana, papel="rapido",
                                sistema=SISTEMA, contexto=8192)
            ventanas.append({"desde": a, "hasta": b, **json.loads(r.model_dump_json())})
        else:
            ventanas.append({"desde": a, "hasta": b, "momentos": [], "tono": "", "apodos": []})
        destino.write_text(json.dumps(previo, ensure_ascii=False, indent=1), encoding="utf-8")
        if aviso:
            aviso("Estudiando la narración", 100 * b / dur)
        a = b
    ia.liberar("rapido")
    momentos = [m for v in ventanas for m in v["momentos"]]
    cuenta: dict[str, int] = {}
    for m in momentos:
        cuenta[m["recurso"]] = cuenta.get(m["recurso"], 0) + 1
    minutos = max(dur / 60, 1e-6)
    previo["resumen"] = {
        "recursos_por_minuto": {k: round(v / minutos, 2) for k, v in sorted(cuenta.items(), key=lambda x: -x[1])},
        "chistes_por_minuto": round(sum(1 for m in momentos if m["funcion"] == "chiste") / minutos, 2),
        "apodos": sorted({x for v in ventanas for x in v["apodos"]}),
        "cortes_en_pausas": cortes_en_pausas(tomas, audio.get("pausas", {}).get("lista", [])),
        "palabras_por_minuto": palabras.get("palabras_por_minuto"),
    }
    previo["completo"] = True
    destino.write_text(json.dumps(previo, ensure_ascii=False, indent=1), encoding="utf-8")
    return previo
