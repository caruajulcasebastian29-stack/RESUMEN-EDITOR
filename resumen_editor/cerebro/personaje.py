"""El personaje: estudia clips de referencia de cómo debe hablar el mapache (los doblajes en broma de
Bad Cat que eligió Jhon) y arma su perfil: forma de hablar, insultos, muletillas, tono, ritmo, gritos,
entonación, y cómo se construye un estallido de rabia.

Cada clip pasa por:
  1. separar la voz de la música
  2. transcribir y separar hablantes (quién dice qué)
  3. medir cada frase con Praat: tono, cuánto sube y baja, intensidad, si la entonación sube al final
  4. escuchar gritos, risas, quejas y llanto (modelo de etiquetado de audio)
  5. el modelo de lenguaje lee las frases, ya con esas medidas, y marca el registro (calma, queja,
     reclamo a gritos, remate…), los recursos (insulto, exageración, acusación, lista de desgracias…)
     y por qué da risa
  6. con todo eso escribe el perfil del personaje, con frases nuevas en su estilo (no copiadas)

Jhon indica qué toma de cada clip: «calma» (cómo narra tranquilo), «rabia» (cómo reclama y estalla) o
«todo». El perfil final junta los dos registros en un solo personaje.
"""
from __future__ import annotations

import json
import statistics
from collections import Counter
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field

from . import audio, ia, memoria, palabras, sonidos, voz
from .aprender import DATOS, ident

CARPETA = DATOS / "personaje"
PERFIL = CARPETA / "perfil.json"
PREFIJO = "personaje:"


class Registro(str, Enum):
    calma = "calma"                  # cuenta tranquilo, en confianza
    susurro = "susurro"              # baja la voz, habla para sí
    queja = "queja"                  # se lamenta, exagera su desgracia
    reclamo_a_gritos = "reclamo_a_gritos"
    grito = "grito"
    remate = "remate"                # la frase final que cierra el chiste (suele llevar la grosería)
    respuesta_seca = "respuesta_seca"  # el otro personaje contesta corto y sin emoción


class Recurso(str, Enum):
    insulto = "insulto"
    groseria = "groseria"
    groseria_cortada = "groseria_cortada"
    exageracion = "exageracion"
    acusacion = "acusacion"
    victimismo = "victimismo"
    lista_de_desgracias = "lista_de_desgracias"
    pregunta_retorica = "pregunta_retorica"
    muletilla = "muletilla"
    apodo = "apodo"
    amenaza_comica = "amenaza_comica"
    adivina_mal = "adivina_mal"
    contraste = "contraste"
    ninguno = "ninguno"


class Linea(BaseModel):
    n: int
    registro: Registro
    recursos: list[Recurso]
    insultos: list[str] = Field(description="insultos o groserías tal como suenan en la frase")
    muletillas: list[str] = Field(description="palabras de relleno o de barrio que repite: pues, oe, vaina…")
    por_que_da_risa: str = Field(description="una frase corta; vacío si no busca risa")


class Lineas(BaseModel):
    lineas: list[Linea]


class Perfil(BaseModel):
    como_habla: str = Field(description="cómo habla en general, en 3-4 frases sencillas")
    actitud: str = Field(description="su actitud ante la vida y ante los demás")
    acento_y_vocabulario: str
    muletillas: list[str]
    insultos_tipicos: list[str]
    como_usa_las_groserias: str
    estructura_del_estallido: list[str] = Field(description="pasos de cómo pasa de la calma al grito y remata")
    cuando_grita: str
    cuando_se_calma: str
    ritmo_y_pausas: str
    entonacion: str
    contraste_con_los_demas: str
    frases_nuevas_en_su_estilo: list[str] = Field(
        description="10 frases NUEVAS que diría este personaje contando una película (no copias del clip)")
    lo_que_nunca_haria: list[str]


SISTEMA = ("Eres un experto en doblaje y comedia latinoamericana. Analizas cómo habla un personaje cómico para "
           "que otro personaje (un mapache narrador de resúmenes de películas) hable igual. Respondes en español, "
           "con palabras sencillas, sin inventar lo que no está en los datos.")

PEDIDO_LINEAS = """Estas son frases de un clip de doblaje en broma ({rol}). Cada frase trae medidas de la voz:
tono (Hz), cuánto sube y baja (semitonos), volumen respecto a lo normal del clip (dB), velocidad
(palabras por segundo), forma de la entonación, y sonidos detectados (grito, risa, queja).

{frases}

Para cada frase (por su número n) marca el registro, los recursos cómicos, los insultos y muletillas que
aparecen tal como suenan, y en pocas palabras por qué da risa. Usa las medidas: si el volumen está muy por
encima de lo normal y se detectó grito, es grito o reclamo a gritos."""

PEDIDO_PERFIL = """Con el análisis de {n} frases de clips de referencia, describe la personalidad y la forma de
hablar del personaje para que el mapache narrador hable igual.

Registros pedidos por Jhon: {roles}. El mapache narra con la calma del registro tranquilo y, solo cuando la
película da rabia (un villano, alguien muy tonto, una traición), estalla con el registro de rabia.

Medidas de la voz por registro:
{medidas}

Frases analizadas (registro · recursos · texto · por qué da risa):
{lineas}

Escribe el perfil. Las frases nuevas deben ser originales, sobre películas, en su estilo y con sus muletillas;
si llevan grosería, córtala a la mitad (por ejemplo «¡puta ma—!»)."""


def _rol_texto(rol: str) -> str:
    return {"calma": "cómo narra tranquilo", "rabia": "cómo reclama y estalla de rabia"}.get(rol, "todo el clip")


def marcar(frases: list[dict], rol: str, avance=None) -> list[dict]:
    """La IA lee las frases (con sus medidas de voz) y marca registro, recursos, insultos y muletillas."""
    marcadas = []
    for i in range(0, len(frases), 12):
        grupo = frases[i:i + 12]
        texto_frases = "\n".join(
            f"n={i + k}: [{f['hablante']}] «{f['texto']}» · tono {f['tono_hz']} Hz · rango {f['rango_st']} st · "
            f"volumen {f.get('sobresale_db', 0):+.1f} dB · {f['palabras_s']} pal/s · {f.get('entonacion', '')}"
            f"{' · ' + ', '.join(f['sonidos']) if f['sonidos'] else ''}" for k, f in enumerate(grupo))
        r = ia.estructurado(PEDIDO_LINEAS.format(rol=_rol_texto(rol), frases=texto_frases), Lineas,
                            papel="experto", sistema=SISTEMA, contexto=8192)
        por_n = {x.n: x for x in r.lineas}
        for k, f in enumerate(grupo):
            x = por_n.get(i + k)
            marcadas.append({**f, **(json.loads(x.model_dump_json()) if x else
                                     {"registro": "calma", "recursos": [], "insultos": [], "muletillas": [],
                                      "por_que_da_risa": ""}), "n": i + k})
        if avance:
            avance(min(1, (i + 12) / max(1, len(frases))))
    return marcadas


def estudiar_clip(video: Path, rol: str = "todo", aviso=None) -> dict:
    vid = ident(video)
    carpeta = CARPETA / vid
    carpeta.mkdir(parents=True, exist_ok=True)
    final = carpeta / "lineas.json"
    if final.exists():
        return json.loads(final.read_text(encoding="utf-8"))

    def paso(m, p):
        if aviso:
            aviso(m, p)
    paso("Separando la voz", 5)
    v, _ = audio.separar(video, carpeta)
    paso("Escuchando qué dice y quién lo dice", 25)
    pa = palabras.analizar(v, carpeta, aviso=lambda m, p: paso(m, 25 + 0.25 * p))
    paso("Midiendo tono, gritos y entonación", 50)
    vo = voz.analizar(v, carpeta, pa, solo_narrador=False)
    oido = sonidos.escuchar(v)
    frases = vo["frases"]
    for f in frases:
        g = Counter()
        for s in oido:
            if f["inicio"] - 1 <= s["t"] <= f["fin"]:
                g.update({k: 1 for k in s["grupos"] if k in ("grito", "risa", "llanto", "suspiro_o_queja")})
        f["sonidos"] = [k for k, _ in g.most_common()]
    paso("Leyendo cada frase", 60)
    marcadas = marcar(frases, rol, lambda p: paso("Leyendo cada frase", 60 + 30 * p))
    datos = {"video": vid, "archivo": video.name, "rol": rol, "lineas": marcadas}
    final.write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")
    memoria.borrar_video(PREFIJO + vid)
    memoria.guardar_filas([{"video": PREFIJO + vid, "inicio": float(m["inicio"]), "funcion": "personaje",
                            "recurso": ",".join(m["recursos"]) or m["registro"], "frase": m["texto"],
                            "por_que": m["por_que_da_risa"] or m["registro"], "tono": m["registro"]}
                           for m in marcadas if m["texto"].strip()])
    paso("Clip estudiado", 100)
    return datos


def _por_registro(lineas: list[dict]) -> dict[str, list[dict]]:
    salida: dict[str, list[dict]] = {}
    for x in lineas:
        salida.setdefault(x["registro"], []).append(x)
    return salida


def _mediana(xs: list[dict], k: str, dec: int = 1):
    vals = [x[k] for x in xs if isinstance(x.get(k), (int, float))]
    return round(statistics.median(vals), dec) if vals else None


def _medidas(lineas: list[dict]) -> str:
    salida = []
    for reg, xs in sorted(_por_registro(lineas).items(), key=lambda kv: -len(kv[1])):
        ent = Counter(x.get("entonacion") for x in xs).most_common(2)
        salida.append(f"- {reg} ({len(xs)} frases): {_mediana(xs, 'palabras_s')} palabras/s · "
                      f"rango {_mediana(xs, 'rango_st')} st · volumen {_mediana(xs, 'sobresale_db')} dB sobre lo normal · "
                      f"tono {_mediana(xs, 'tono_hz')} Hz · entonación más común: "
                      f"{', '.join(f'{e} ({n})' for e, n in ent)}")
    return "\n".join(salida)


def numeros(lineas: list[dict]) -> dict:
    """Las medidas que el generador de voz y el guionista usan como objetivo."""
    por_reg = {reg: {"frases": len(xs), "palabras_s": _mediana(xs, "palabras_s", 2),
                     "rango_st": _mediana(xs, "rango_st"), "sobre_lo_normal_db": _mediana(xs, "sobresale_db"),
                     "tono_hz": _mediana(xs, "tono_hz")}
               for reg, xs in _por_registro(lineas).items()}
    recursos = Counter(r for x in lineas for r in x["recursos"] if r != "ninguno")
    return {"por_registro": por_reg, "recursos": dict(recursos.most_common()),
            "insultos": [k for k, _ in Counter(i.lower() for x in lineas for i in x["insultos"]).most_common(20)],
            "muletillas": [k for k, _ in Counter(m.lower() for x in lineas for m in x["muletillas"]).most_common(15)],
            "sube_al_final": round(sum(x.get("entonacion") == "sube_al_final" for x in lineas) / max(1, len(lineas)), 2)}


def armar_perfil(aviso=None) -> dict:
    clips = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(CARPETA.glob("*/lineas.json"))]
    if not clips:
        raise ValueError("Todavía no le enseñaste ningún clip del personaje.")
    if aviso:
        aviso("Escribiendo la personalidad del personaje", 92)
    todas = [x for c in clips for x in c["lineas"]]
    lineas = "\n".join(f"- {x['registro']} · {','.join(x['recursos'])} · «{x['texto']}» · {x['por_que_da_risa']}"
                       for x in todas)[:12000]
    roles = ", ".join(f"{c['archivo']} = {_rol_texto(c['rol'])}" for c in clips)
    r = ia.estructurado(PEDIDO_PERFIL.format(n=len(todas), roles=roles, medidas=_medidas(todas), lineas=lineas),
                        Perfil, papel="escritor", sistema=SISTEMA, contexto=12288, temperatura=0.5)
    p = {**json.loads(r.model_dump_json()), "numeros": numeros(todas),
         "clips": [{"video": c["video"], "archivo": c["archivo"], "rol": c["rol"], "frases": len(c["lineas"])}
                   for c in clips]}
    PERFIL.write_text(json.dumps(p, ensure_ascii=False, indent=1), encoding="utf-8")
    return p


def perfil() -> dict | None:
    return json.loads(PERFIL.read_text(encoding="utf-8")) if PERFIL.exists() else None


def texto(p: dict | None = None) -> str:
    """El perfil en frases para las instrucciones del guionista y del modelo propio."""
    p = p or perfil()
    if not p:
        return ""
    n = p.get("numeros", {})
    lineas = ["PERSONALIDAD DEL MAPACHE (estudiada de los clips de referencia):",
              f"- Cómo habla: {p['como_habla']}", f"- Actitud: {p['actitud']}",
              f"- Acento y vocabulario: {p['acento_y_vocabulario']}",
              f"- Muletillas: {', '.join(p['muletillas'][:12])}",
              f"- Insultos típicos: {', '.join(p['insultos_tipicos'][:12])}",
              f"- Groserías: {p['como_usa_las_groserias']}",
              "- Estallido de rabia: " + " → ".join(p["estructura_del_estallido"]),
              f"- Cuándo grita: {p['cuando_grita']}", f"- Cuándo se calma: {p['cuando_se_calma']}",
              f"- Ritmo y pausas: {p['ritmo_y_pausas']}", f"- Entonación: {p['entonacion']}",
              f"- Contraste: {p['contraste_con_los_demas']}",
              "- Nunca: " + "; ".join(p["lo_que_nunca_haria"][:8]),
              "- Frases de ejemplo en su estilo: " + " | ".join(p["frases_nuevas_en_su_estilo"][:8])]
    reg = n.get("por_registro", {})
    if reg.get("calma") and reg.get("reclamo_a_gritos"):
        lineas.append(f"- Habla a {reg['calma']['palabras_s']} palabras/s tranquilo y a "
                      f"{reg['reclamo_a_gritos']['palabras_s']} cuando reclama.")
    return "\n".join(lineas)


def quitar(video_id: str) -> None:
    import shutil
    carpeta = (CARPETA / video_id).resolve()
    if CARPETA.resolve() in carpeta.parents and carpeta.exists():
        shutil.rmtree(carpeta)
    memoria.borrar_video(PREFIJO + video_id)
