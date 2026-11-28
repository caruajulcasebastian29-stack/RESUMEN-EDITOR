"""Comprensión: el editor experto «ve» el video entero y lo describe como lo haría una persona.

Junta, tramo por tramo (30 s), todo lo que midieron las demás capas:
  lo que se ve en cada toma (visión), lo que dice el narrador y los demás (transcripción), los textos
  en pantalla, los sonidos (gritos, risas, golpes, efectos), el ánimo de la música y sus cambios, los
  cortes y transiciones, el zoom y el movimiento, el encuadre (primer plano o general) y la voz
  (si sube, si grita).
Con eso escribe para cada tramo: qué pasa en la historia, cómo está editado, cuál es la intención y por
qué funciona. Después escribe la descripción del video completo y lo compara con lo que ya sabe del
canal (sus reglas): qué hace igual, qué hace distinto y qué conviene copiar.
"""
from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field

from . import ia

TRAMO_S = 30.0


class Tramo(BaseModel):
    que_pasa: str = Field(description="qué pasa en la historia en este tramo, en 2-3 frases")
    como_esta_editado: str = Field(description="cortes, música, efectos, textos y encuadre, en 2-3 frases")
    intencion: str = Field(description="qué busca el editor aquí: enganchar, hacer reír, tensión, explicar…")
    por_que_funciona: str
    momento_clave: str = Field(description="el instante más fuerte del tramo y qué lo hace fuerte; vacío si no hay")


class Global(BaseModel):
    descripcion: str = Field(description="cómo es el video completo, en un párrafo")
    estructura: list[str] = Field(description="las partes del video en orden, con su segundo de inicio")
    ritmo: str = Field(description="cómo se mueve el ritmo a lo largo del video")
    lo_que_hace_igual_al_canal: list[str]
    lo_que_hace_distinto: list[str]
    para_copiar: list[str] = Field(description="técnicas concretas que conviene usar en nuestros resúmenes")


SISTEMA = ("Eres el editor principal de un canal de resúmenes de películas. Miras videos de referencia con "
           "todos los datos medidos y explicas, en español sencillo, qué pasa y cómo está hecho. No inventas lo "
           "que no está en los datos.")

PEDIDO_TRAMO = """Tramo {a:.0f}–{b:.0f} s de un resumen de película. Lo que midieron las herramientas:

TOMAS (inicio · entrada · lo que se ve · encuadre · movimiento):
{tomas}

VOZ (lo que se dice, quién, y cómo suena):
{voz}

TEXTOS EN PANTALLA: {textos}
SONIDOS: {sonidos}
MÚSICA: {musica}

Antes de este tramo pasó: {antes}

Describe el tramo."""

PEDIDO_GLOBAL = """Este es el resumen tramo por tramo de un video de referencia ({archivo}, {dur:.0f} s):

{tramos}

Medidas generales: {medidas}

Lo que ya sabes del canal (tus reglas):
{reglas}

Describe el video completo y compáralo con lo que ya sabes."""


def _en(lista, a, b, ini="inicio", fin="fin"):
    return [x for x in lista if x.get(ini, 0) < b and x.get(fin, x.get(ini, 0)) >= a]


def analizar(carpeta: Path, archivo: str, dur: float, tomas: list[dict], vistas: list[dict], palabras: dict,
             voz: dict, texto: dict, sonidos: dict, musica: dict, efectos: dict, encuadre: dict,
             reglas: str = "", aviso=None) -> dict:
    destino = carpeta / "comprension.json"
    hecho = json.loads(destino.read_text(encoding="utf-8")) if destino.exists() else {"tramos": []}
    if hecho.get("global"):
        return hecho
    vista = {v["n"]: v for v in vistas}
    ef = {e["n"]: e for e in efectos.get("tomas", [])}
    en = {e["n"]: e for e in encuadre.get("tomas", [])}
    frases_voz = voz.get("frases", [])
    n_tramos = max(1, int(dur // TRAMO_S) + (1 if dur % TRAMO_S > 3 else 0))
    for k in range(len(hecho["tramos"]), n_tramos):
        a, b = k * TRAMO_S, min(dur, (k + 1) * TRAMO_S)
        lineas_tomas = []
        for t in _en(tomas, a, b)[:30]:
            v, e, c = vista.get(t["n"], {}), ef.get(t["n"], {}), en.get(t["n"], {})
            mov = ", ".join(x for x in [e.get("zoom") and f"zoom {e['zoom']}", e.get("paneo") and "paneo",
                                        e.get("movimiento"), e.get("tinte") and f"tinte {e['tinte']}",
                                        e.get("blanco_negro") and "blanco y negro"] if x)
            lineas_tomas.append(f"- {t['inicio']:.1f}s · {t.get('entrada', '')} · [{v.get('tipo', '')}] "
                                f"{v.get('descripcion', '')} · {v.get('emocion', '')} · {c.get('plano', '')} · {mov}")
        lineas_voz = []
        for h in _en(palabras.get("tramos", []), a, b):
            m = next((f for f in frases_voz if abs(f["inicio"] - h["inicio"]) < 0.05), None)
            como = (f" ({m.get('entonacion', '')}, {m.get('sobresale_db', 0):+.0f} dB, {m.get('palabras_s', '')} pal/s)"
                    if m else "")
            lineas_voz.append(f"- {h['inicio']:.1f}s [{h['hablante']}] «{h['texto']}»{como}")
        textos = "; ".join(f"{x['tipo']}: «{x['texto']}» ({x['inicio']:.0f}s)"
                           for x in _en(texto.get("elementos", []), a, b) if x["tipo"] != "marca") or "ninguno"
        sons = "; ".join(f"{x['tipo']} {x['inicio']:.0f}s" for x in _en(sonidos.get("eventos", []), a, b)) or "ninguno"
        animos = [s["musica"] for s in sonidos.get("por_segundo", []) if a <= s["t"] < b and s.get("musica")]
        cambios = [c for c in musica.get("cambios_de_musica", []) if a <= c < b]
        mus = (f"ánimo {max(set(animos), key=animos.count) if animos else 'sin dato'}; "
               f"cambia en {', '.join(f'{c:.0f}s' for c in cambios) or 'ningún momento'}")
        antes = " ".join(t["que_pasa"] for t in hecho["tramos"][-2:]) or "es el inicio del video"
        r = ia.estructurado(PEDIDO_TRAMO.format(a=a, b=b, tomas="\n".join(lineas_tomas) or "-",
                                                voz="\n".join(lineas_voz) or "- (sin voz)", textos=textos,
                                                sonidos=sons, musica=mus, antes=antes),
                            Tramo, papel="experto", sistema=SISTEMA, contexto=8192)
        hecho["tramos"].append({"desde": a, "hasta": b, **json.loads(r.model_dump_json())})
        destino.write_text(json.dumps(hecho, ensure_ascii=False, indent=1), encoding="utf-8")
        if aviso:
            aviso("Describiendo lo que ve", 100 * (k + 1) / (n_tramos + 1))
    resumen_tramos = "\n".join(f"{t['desde']:.0f}s: {t['que_pasa']} | edición: {t['como_esta_editado']} | "
                               f"intención: {t['intencion']}" for t in hecho["tramos"])[:12000]
    medidas = json.dumps({"tomas": len(tomas), "cortes_por_minuto": round(len(tomas) / max(dur / 60, 1e-6), 1),
                          "sonidos": sonidos.get("resumen"), "encuadre": encuadre.get("resumen"),
                          "textos": texto.get("resumen", {}).get("por_minuto")}, ensure_ascii=False)
    g = ia.estructurado(PEDIDO_GLOBAL.format(archivo=archivo, dur=dur, tramos=resumen_tramos, medidas=medidas,
                                             reglas=reglas[:5000] or "(todavía no tiene reglas)"),
                        Global, papel="experto", sistema=SISTEMA, contexto=12288)
    hecho["global"] = json.loads(g.model_dump_json())
    destino.write_text(json.dumps(hecho, ensure_ascii=False, indent=1), encoding="utf-8")
    return hecho


def filas_memoria(video_id: str, c: dict) -> list[dict]:
    """Lo que entendió, para que el guionista lo encuentre al buscar en la memoria."""
    filas = [{"video": video_id, "inicio": float(t["desde"]), "funcion": "comprension", "recurso": t["intencion"][:80],
              "frase": t["como_esta_editado"], "por_que": t["por_que_funciona"], "tono": ""} for t in c["tramos"]]
    for x in c.get("global", {}).get("para_copiar", []):
        filas.append({"video": video_id, "inicio": 0.0, "funcion": "tecnica", "recurso": "para_copiar",
                      "frase": x, "por_que": "lo vio en un video de referencia", "tono": ""})
    return filas
