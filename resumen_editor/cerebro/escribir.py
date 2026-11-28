"""Escribir la narración nueva del mapache, hecho por hecho.

Para cada bloque de la historia (unos 60-90 s del video de la App 1):
  - mide cuántas palabras caben en las imágenes de ese bloque (velocidad aprendida de las referencias)
  - busca en la memoria ejemplos reales de canales parecidos para esa emoción y función
  - pide al modelo escritor las frases, con las marcas del guion ([rata], [tarjeta: …], [gesto: …]…)
  - revisa con reglas fijas (largo, modo rata, groserías, muletillas prohibidas) y, si falla,
    devuelve el bloque al escritor con los errores concretos para que lo corrija.

Salida: guion.json con el formato que ya usan la voz y el montaje (frases con "fuente").
"""
from __future__ import annotations

import json
import re
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field

from .. import guion as G
from ..config import estilo, preferencias
from . import conocimiento, ia, memoria

BLOQUE_S = 75.0
INTENTOS = 3


class Tono(str, Enum):
    tranquilo = "tranquilo"
    burla = "burla"
    frustrado = "frustrado"
    furioso = "furioso"
    sorpresa = "sorpresa"
    triste = "triste"
    misterio = "misterio"


class Velocidad(str, Enum):
    lenta = "lenta"
    normal = "normal"
    rapida = "rapida"


class Linea(BaseModel):
    hecho: int = Field(description="número del hecho que cuenta esta frase")
    texto: str = Field(description="lo que dice el mapache, con las marcas del guion donde correspondan")
    tono: Tono = Field(description="cómo lo dice el mapache")
    velocidad: Velocidad = Field(description="lenta para explicar o antes de un remate; rápida en listas, acción o frustración")


class Bloque(BaseModel):
    lineas: list[Linea]


def _sistema() -> str:
    n = estilo("narrador")
    reg = n["registros"]
    return f"""Eres el guionista de un canal de resúmenes de películas en YouTube. El narrador es un {n['personaje']['especie']}:
{n['personaje']['descripcion']} Habla con acento {n['personaje']['acento']}.

Cómo narra:
- Registro normal: {reg['narrando']['tono']}. Es casi todo el video.
- Frustrado: {reg['frustrado']['uso']}. {reg['frustrado']['tono']}. Como mucho {reg['frustrado']['por_minuto_max']} veces por minuto.
- Modo rata (marca [rata] … [/rata]): solo cuando la película da rabia ({', '.join(reg['rata']['motivos_validos'])}).
  Estructura: {' → '.join(reg['rata']['estructura'])}. Entre {reg['rata']['por_video']['min']} y {reg['rata']['por_video']['max']} veces en TODO el video.
- Velocidad: lenta {n['ritmo']['variacion']['lenta']}; rápida {n['ritmo']['variacion']['rapida']}; normal el resto.
- Groserías: {n['groserias']['cuando']}. Solo dentro del modo rata, cortadas a la mitad con la marca [groseria: texto—], por ejemplo
  {', '.join(n['groserias']['ejemplos'])}. Como mucho una cada {n['groserias']['minimo_segundos_entre']} segundos.
- Eufemismos: {', '.join(f'«{v}» en vez de «{k}»' for k, v in n['eufemismos'].items())}.
- Nunca: {'; '.join(n['prohibido'])}.

Marcas disponibles (van dentro del texto, donde ocurren):
{chr(10).join(f'  {k}: {v}' for k, v in n['marcas_guion'].items())}

Escribes para ser dicho en voz alta: frases cortas, ritmo de conversación, sin acotaciones ni narrador neutro.
No inventas hechos: cuentas solo lo que está en el mapa de la historia.

{conocimiento.guia()}"""


PEDIDO = """Película: {titulo} ({genero}). {premisa}
Personajes: {personajes}

Lo que ya dijo el mapache justo antes:
{anterior}

Hechos de este bloque (cada uno con los segundos de imagen disponibles y cuántas palabras caben):
{hechos}

Ejemplos reales de canales que funcionan, para que aprendas el estilo (no los copies):
{ejemplos}

{extra}
El mapache aparece en pantalla (plano completo, reaccionando) con [gesto: emoción] unas {insertos} veces por minuto,
solo en los momentos de reacción fuerte: un remate, algo tonto, algo indignante. Emociones: tranquilo, burla,
frustrado, furioso, sorpresa, triste, misterio.
Escribe las frases del mapache para estos hechos, en orden. Respeta el número de palabras de cada hecho
(±15 %). Usa marcas donde aporten: [tarjeta: …] cuando pasa el tiempo, [lugar: …] al cambiar de sitio,
[rotulo: …] la primera vez que aparece un personaje importante, [gesto: emoción] en los momentos de reacción."""

PEDIDO_GANCHO = """Escribe el gancho del video (los primeros {seg} segundos, unas {palabras} palabras).
Estructura que usan los canales que más funcionan: {plantilla}.
Ganchos reales aprendidos: {ganchos}
Película: {titulo} ({genero}). {premisa} Final: {final}
Debe dar ganas de quedarse sin contar el final. Puede incluir [tarjeta: TÍTULO EN BROMA]."""


def _palabras_que_caben(seg: float, ppm: float) -> int:
    return max(3, round(seg * ppm / 60))


def _ejemplos(hechos: list[dict]) -> str:
    try:
        emociones = ", ".join(dict.fromkeys(h["emocion"] for h in hechos))
        try:
            conocimiento.sembrar()
        except Exception:
            pass
        ej = memoria.buscar(f"narración con humor en escena de {emociones}", k=6)
    except Exception:
        ej = []
    return "\n".join(f"- ({e['funcion']}, {e['recurso']}) «{e['frase']}» → {e['por_que']}" for e in ej) or "—"


def _revisar(lineas: list[dict], hechos: list[dict], ppm: float, tiempo: float, estado: dict) -> list[str]:
    """Errores concretos del bloque; vacío si está bien."""
    errores = []
    prohibidas = ["y es aquí donde todo cambia", "se menciona que", "en este video", "suscríbete"]
    for h in hechos:
        texto = " ".join(x["texto"] for x in lineas if x["hecho"] == h["id"])
        hablado = G.MARCA.sub("", texto)
        n = len(hablado.split())
        cabe = _palabras_que_caben(h["fin"] - h["inicio"], ppm)
        if n == 0:
            errores.append(f"El hecho {h['id']} quedó sin narrar.")
        elif n > cabe * 1.25:
            errores.append(f"El hecho {h['id']} tiene {n} palabras y solo caben {cabe}: acórtalo.")
        elif n < cabe * 0.6:
            errores.append(f"El hecho {h['id']} tiene {n} palabras y caben {cabe}: desarróllalo un poco más.")
    todo = " ".join(x["texto"] for x in lineas)
    for p in prohibidas:
        if p in todo.lower():
            errores.append(f"Quita la muletilla prohibida «{p}».")
    ratas = todo.count("[rata]")
    maximo = estilo("narrador")["registros"]["rata"]["por_video"]["max"]
    if estado["ratas"] + ratas > maximo:
        errores.append(f"Ya van {estado['ratas']} modos rata y el máximo del video es {maximo}: quita el de este bloque.")
    gros = len(re.findall(r"\[groseria:", todo))
    minimo = estilo("narrador")["groserias"]["minimo_segundos_entre"]
    if gros > 1 or (gros and tiempo - estado["ultima_groseria"] < minimo):
        errores.append(f"Demasiado pronto para otra grosería (mínimo {minimo} s entre una y otra).")
    if "[groseria:" in todo and "[rata]" not in todo and not estado["en_rata"]:
        errores.append("Las groserías solo van dentro del modo rata.")
    for x in lineas:
        if todo.count("[rata]") != todo.count("[/rata]") and not estado["en_rata"]:
            errores.append("Cada [rata] debe cerrarse con [/rata] dentro del mismo bloque.")
            break
    return errores


def escribir(carpeta: Path, mapa: dict, manual: dict, aviso=None) -> Path:
    destino = carpeta / "guion.json"
    parcial = carpeta / "guion.parcial.json"
    if destino.exists():
        return destino
    ppm = float((manual.get("palabras_por_minuto") or {}).get("mediana") or 185)
    peli = mapa["pelicula"]
    personajes = "; ".join(f"{p['nombre']} ({p['papel']}, {p['aspecto']})" for p in mapa["personajes"]) or "—"
    hechos = mapa["hechos"]
    estado = json.loads(parcial.read_text(encoding="utf-8")) if parcial.exists() else {
        "frases": [], "hecho_siguiente": 0, "ratas": 0, "ultima_groseria": -1e9, "en_rata": False, "gancho": False}
    gustos = preferencias()
    extra = ""
    if gustos.get("rechazado") or gustos.get("aprobado"):
        extra = ("Gustos de Jhon aprendidos de sus revisiones:\n" +
                 "\n".join(f"- No le gustó: {x}" for x in gustos.get("rechazado", [])[-6:]) + "\n" +
                 "\n".join(f"- Le gustó: {x}" for x in gustos.get("aprobado", [])[-6:]) + "\n")
    sistema = _sistema()
    insertos = (manual.get("insertos_personaje_por_minuto") or {}).get("mediana") or 1.5

    if not estado["gancho"]:
        g = estilo("narrador")["gancho"]
        seg = sum(g["duracion_s"]) / 2
        ganchos = "; ".join(f"«{x['frase']}» ({x['tipo']})" for x in manual.get("ganchos", [])[:5]) or "—"
        texto = ia.preguntar(PEDIDO_GANCHO.format(seg=seg, palabras=_palabras_que_caben(seg, ppm),
                                                  plantilla=" → ".join(g["plantilla"]), ganchos=ganchos,
                                                  titulo=peli["titulo_probable"] or "la película",
                                                  genero=peli["genero"], premisa=peli["premisa"], final=peli["final"]),
                             papel="escritor", sistema=sistema, temperatura=0.8)
        # imágenes del gancho: los momentos más fuertes, sin el último quinto (no se adelanta el final)
        limite = hechos[-1]["fin"] * 0.8 if hechos else 0
        fuertes = sorted((h for h in hechos if h["fin"] <= limite), key=lambda h: -h["importancia"])[:5]
        fuentes = sorted([[h["inicio"], h["fin"]] for h in fuertes]) or [[0, seg]]
        estado["frases"].append({"texto": texto.strip().strip('"'), "fuente": fuentes[0], "fuentes": fuentes,
                                 "gancho": True})
        estado["gancho"] = True
        parcial.write_text(json.dumps(estado, ensure_ascii=False, indent=1), encoding="utf-8")

    i = estado["hecho_siguiente"]
    while i < len(hechos):
        bloque = [hechos[i]]
        while i + len(bloque) < len(hechos) and hechos[i + len(bloque)]["fin"] - bloque[0]["inicio"] <= BLOQUE_S:
            bloque.append(hechos[i + len(bloque)])
        lista = "\n".join(f"{h['id']}. [{h['fin'] - h['inicio']:.0f} s → {_palabras_que_caben(h['fin'] - h['inicio'], ppm)} "
                          f"palabras] {h['que_pasa']} (emoción: {h['emocion']}; personajes: {', '.join(h['personajes'])})"
                          for h in bloque)
        anterior = "\n".join(f["texto"] for f in estado["frases"][-4:]) or "(es el comienzo)"
        prompt = PEDIDO.format(titulo=peli["titulo_probable"] or "sin título", genero=peli["genero"],
                               premisa=peli["premisa"], personajes=personajes, anterior=anterior, hechos=lista,
                               ejemplos=_ejemplos(bloque), extra=extra, insertos=insertos)
        errores: list[str] = []
        lineas: list[dict] = []
        for intento in range(INTENTOS):
            nota = ("\n\nTu versión anterior tenía estos problemas, corrígelos:\n- " + "\n- ".join(errores)) if errores else ""
            r = ia.estructurado(prompt + nota, Bloque, papel="escritor", sistema=sistema, temperatura=0.75,
                                contexto=12288)
            lineas = [x.model_dump(mode="json") for x in r.lineas]
            errores = _revisar(lineas, bloque, ppm, bloque[0]["inicio"], estado)
            if not errores:
                break
        for h in bloque:
            propias = [x for x in lineas if x["hecho"] == h["id"]]
            if not propias:
                continue
            for x in propias:
                if "[groseria:" in x["texto"]:
                    estado["ultima_groseria"] = h["inicio"]
                estado["ratas"] += x["texto"].count("[rata]")
            # cada línea es una frase propia (su propio tono y velocidad); comparten el tramo de imagen del hecho
            total = sum(len(G.MARCA.sub("", x["texto"]).split()) for x in propias) or 1
            t0 = h["inicio"]
            for x in propias:
                parte = (h["fin"] - h["inicio"]) * len(G.MARCA.sub("", x["texto"]).split()) / total
                estado["frases"].append({"texto": x["texto"].strip(), "fuente": [round(t0, 2), round(t0 + parte, 2)],
                                         "hecho": h["id"], "tono": x["tono"], "velocidad": x["velocidad"],
                                         "avisos": errores or None})
                t0 += parte
        i += len(bloque)
        estado["hecho_siguiente"] = i
        parcial.write_text(json.dumps(estado, ensure_ascii=False, indent=1), encoding="utf-8")
        if aviso:
            aviso("Escribiendo la narración", 100 * i / max(1, len(hechos)))

    guion = {"titulo": peli["titulo_probable"],
             "frases": [{"id": k + 1, **f} for k, f in enumerate(estado["frases"])]}
    destino.write_text(json.dumps(guion, ensure_ascii=False, indent=1), encoding="utf-8")
    parcial.unlink(missing_ok=True)
    ia.liberar("escritor")
    return destino


PEDIDO_REHACER = """Jhon rechazó este tramo del video. Su comentario: «{comentario}»
Lo que el mapache dijo antes: {anterior}
Lo que dirá después: {siguiente}

Hechos de este tramo (con las palabras que caben):
{hechos}

Versión rechazada:
{rechazada}

Escribe una versión nueva que corrija lo que Jhon pidió y empalme con lo de antes y lo de después."""


def rehacer(frases: list[dict], mapa: dict, manual: dict, comentario: str, anterior: str, siguiente: str) -> list[dict]:
    """Nueva versión de un lote rechazado, para los mismos hechos y el mismo tiempo de imagen."""
    ppm = float((manual.get("palabras_por_minuto") or {}).get("mediana") or 185)
    por_id = {h["id"]: h for h in mapa["hechos"]}
    salida = []
    gancho = [f for f in frases if f.get("gancho")]
    resto = [f for f in frases if not f.get("gancho")]
    for f in gancho:  # el gancho se reescribe solo, con el comentario
        texto = ia.preguntar(f"Reescribe este gancho de un resumen de película. Comentario de Jhon: «{comentario}».\n"
                             f"Gancho anterior: {f['texto']}\nSolo el texto nuevo, mismo largo.",
                             papel="escritor", sistema=_sistema(), temperatura=0.8)
        salida.append({**f, "texto": texto.strip().strip('"')})
    hechos = [por_id[f["hecho"]] for f in resto if f.get("hecho") in por_id]
    if hechos:
        lista = "\n".join(f"{h['id']}. [{_palabras_que_caben(h['fin'] - h['inicio'], ppm)} palabras] {h['que_pasa']}"
                          for h in hechos)
        r = ia.estructurado(PEDIDO_REHACER.format(comentario=comentario or "sin comentario: no le convenció",
                                                  anterior=anterior or "—", siguiente=siguiente or "—", hechos=lista,
                                                  rechazada="\n".join(f["texto"] for f in resto)),
                            Bloque, papel="escritor", sistema=_sistema(), temperatura=0.85, contexto=12288)
        for h in hechos:
            propias = [x for x in r.lineas if x.hecho == h["id"]]
            total = sum(len(G.MARCA.sub("", x.texto).split()) for x in propias) or 1
            t0 = h["inicio"]
            for x in propias:
                parte = (h["fin"] - h["inicio"]) * len(G.MARCA.sub("", x.texto).split()) / total
                salida.append({"texto": x.texto.strip(), "fuente": [round(t0, 2), round(t0 + parte, 2)],
                               "hecho": h["id"], "tono": x.tono.value, "velocidad": x.velocidad.value})
                t0 += parte
    ia.liberar("escritor")
    return salida
