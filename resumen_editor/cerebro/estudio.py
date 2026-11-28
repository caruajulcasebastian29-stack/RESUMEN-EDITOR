"""Estudio del conocimiento: la IA lee lo que se analizó de los videos y lo aprende de verdad.

No basta con guardar las notas en la memoria: aquí el modelo
  1. LEE cada nota (los 8 videos de fábrica, el tono del narrador, la comparativa, el perfil del
     personaje y los videos que Jhon le enseñó) y escribe con sus propias palabras las REGLAS del canal,
     cada una con su ejemplo y cuándo se aplica;
  2. JUNTA las reglas repetidas de distintos videos en reglas generales;
  3. SE TOMA UN EXAMEN: de trozos de las notas se sacan preguntas con su respuesta correcta; el modelo
     responde usando su memoria y un juez revisa. Lo que falla se vuelve a estudiar (pasa a regla de
     refuerzo) y se repite el examen de lo fallado;
  4. CREA un modelo propio en Ollama («mapache-editor»): el modelo rápido con las reglas, la guía y la
     personalidad del mapache ya puestas en sus instrucciones. Así cada vez que la app lo usa ya «sabe».

Se repite solo cuando cambia el conocimiento. Lo leído queda guardado; si se cierra la app, sigue.
"""
from __future__ import annotations

import hashlib
import json
import random
from enum import Enum

from pydantic import BaseModel, Field

from . import conocimiento, ia, memoria
from .aprender import DATOS, FICHAS

CARPETA = DATOS / "cerebro"
REGLAS = CARPETA / "reglas.json"
EXAMEN = CARPETA / "examen.json"
ESTADO = CARPETA / "estudio_estado.json"
PREFIJO = "regla:"
PREGUNTAS = 24
APRUEBA = 0.75


class Tema(str, Enum):
    gancho = "gancho"
    estructura = "estructura"
    narracion = "narracion"
    humor = "humor"
    personaje = "personaje"
    voz = "voz"
    cortes = "cortes"
    transiciones = "transiciones"
    musica = "musica"
    sonido = "sonido"
    texto_pantalla = "texto_pantalla"
    efectos = "efectos"
    memes = "memes"
    cierre = "cierre"


class Regla(BaseModel):
    tema: Tema
    regla: str = Field(description="la regla, en una frase clara y concreta (con números si los hay)")
    ejemplo: str = Field(description="un ejemplo real sacado del texto")
    cuando: str = Field(description="en qué momento del video o de la película se aplica")


class Reglas(BaseModel):
    reglas: list[Regla]


class Pregunta(BaseModel):
    pregunta: str
    respuesta: str = Field(description="la respuesta correcta, corta, sacada del texto")


class Juicio(BaseModel):
    correcta: bool
    falta: str = Field(description="qué le faltó o qué dijo mal; vacío si está bien")


SISTEMA_ESTUDIO = ("Eres el editor principal de un canal de resúmenes de películas con un narrador mapache. "
                   "Estudias análisis de videos de referencia para aprender cómo se hacen. Respondes en español "
                   "sencillo, con datos concretos, sin inventar.")

PEDIDO_REGLAS = """Lee este análisis ({fuente}) y escribe las reglas que enseña para hacer nuestros resúmenes:
cómo engancha, cómo cuenta, cómo bromea, cómo habla el personaje, cada cuánto corta, qué música pone, qué
textos pone, qué efectos, cómo cierra. Solo reglas que el texto respalde; entre 6 y 14.

{texto}"""

PEDIDO_JUNTAR = """Estas son reglas del tema «{tema}» sacadas de distintos videos. Junta las que dicen lo mismo,
quita las contradictorias si una tiene menos respaldo, y deja como máximo 10 reglas generales, claras y con
números cuando los haya. Cada regla con su mejor ejemplo.

{reglas}"""

PEDIDO_PREGUNTA = """De este fragmento de un análisis, saca UNA pregunta concreta que un editor del canal debería
saber responder, con su respuesta correcta y corta.

{texto}"""

PEDIDO_JUEZ = """Pregunta: {pregunta}
Respuesta correcta: {correcta}
Respuesta del alumno: {alumno}

¿La respuesta del alumno dice lo mismo que la correcta (aunque con otras palabras)? Si le falta lo
importante o se equivoca en un dato, no es correcta."""


def _estado(**cambios) -> dict:
    CARPETA.mkdir(parents=True, exist_ok=True)
    e = json.loads(ESTADO.read_text(encoding="utf-8")) if ESTADO.exists() else {}
    if cambios:
        e.update(cambios)
        ESTADO.write_text(json.dumps(e, ensure_ascii=False, indent=1), encoding="utf-8")
    return e


def _reglas() -> dict:
    return json.loads(REGLAS.read_text(encoding="utf-8"))["por_tema"] if REGLAS.exists() else {}


def estado() -> dict:
    e = {k: v for k, v in _estado().items() if k != "leidas"}
    e["reglas"] = sum(len(v) for v in _reglas().values())
    if EXAMEN.exists():
        ex = json.loads(EXAMEN.read_text(encoding="utf-8"))
        e["examen"] = {k: v for k, v in ex.items() if k != "preguntas"}
        e["examen"]["ejemplos"] = [{k: p[k] for k in ("pregunta", "respuesta", "alumno", "correcta")}
                                   for p in ex["preguntas"][:6]]
    try:
        e["modelo_propio"] = ia.nombre("experto") == ia.MODELOS["experto"]
        e["al_dia"] = e.get("huella") == huella()
    except Exception:
        pass
    return e


def _fuentes() -> list[tuple[str, str]]:
    """Todo lo que debe estudiar: notas de fábrica, el perfil del personaje y los videos que le enseñó."""
    salida = [(r.stem, r.read_text(encoding="utf-8")) for r in sorted((conocimiento.CARPETA / "notas").glob("*.md"))]
    from . import personaje
    if personaje.perfil():
        salida.append(("personaje", personaje.texto()))
    for f in sorted(FICHAS.glob("*/ficha.json")):
        ficha = json.loads(f.read_text(encoding="utf-8"))
        salida.append((f"video {ficha.get('archivo', f.parent.name)}", json.dumps(
            {k: ficha.get(k) for k in ("tomas", "musica", "texto", "efectos", "ritmo", "sonidos", "encuadre",
                                       "narracion", "gancho", "voz", "comprension")}, ensure_ascii=False)[:9000]))
    return salida


def huella() -> str:
    h = hashlib.sha1()
    for nombre, texto in _fuentes():
        h.update(nombre.encode())
        h.update(texto.encode())
    h.update(conocimiento.guia().encode())
    return h.hexdigest()[:16]


def _trozos(texto: str, tam: int = 5500) -> list[str]:
    partes, actual = [], ""
    for bloque in texto.split("\n\n"):
        if len(actual) + len(bloque) > tam and actual:
            partes.append(actual)
            actual = ""
        actual += bloque + "\n\n"
    if actual.strip():
        partes.append(actual)
    return partes


def _leer_y_sacar_reglas(aviso) -> list[dict]:
    hecho = _estado().get("leidas", {})
    fuentes = _fuentes()
    vigentes = {}
    for k, (nombre, texto) in enumerate(fuentes):
        clave = nombre + ":" + hashlib.sha1(texto.encode()).hexdigest()[:8]
        if clave not in hecho:
            de_esta = []
            for trozo in _trozos(texto):
                r = ia.estructurado(PEDIDO_REGLAS.format(fuente=nombre, texto=trozo), Reglas, papel="rapido",
                                    sistema=SISTEMA_ESTUDIO, contexto=8192)
                de_esta += [{**json.loads(x.model_dump_json()), "fuente": nombre} for x in r.reglas]
            hecho[clave] = de_esta
            _estado(leidas=hecho)
        vigentes[clave] = hecho[clave]
        aviso(f"Leyendo y sacando reglas ({k + 1} de {len(fuentes)})", 5 + 45 * (k + 1) / len(fuentes))
    return [r for v in vigentes.values() for r in v]


def _juntar(crudas: list[dict], aviso) -> dict:
    por_tema: dict[str, list[dict]] = {}
    for r in crudas:
        por_tema.setdefault(r["tema"], []).append(r)
    final = {}
    for k, (tema, rs) in enumerate(sorted(por_tema.items())):
        if len(rs) <= 4:
            final[tema] = rs
        else:
            fuentes = sorted({r["fuente"] for r in rs})
            lista = "\n".join(f"- [{r['fuente']}] {r['regla']} (ej.: {r['ejemplo']}; cuándo: {r['cuando']})"
                              for r in rs)
            j = ia.estructurado(PEDIDO_JUNTAR.format(tema=tema, reglas=lista[:10000]), Reglas, papel="rapido",
                                sistema=SISTEMA_ESTUDIO, contexto=8192)
            final[tema] = [{**json.loads(x.model_dump_json()), "fuente": f"{len(fuentes)} fuentes"} for x in j.reglas]
        aviso(f"Ordenando lo aprendido ({tema})", 50 + 15 * (k + 1) / len(por_tema))
    return final


def _texto_reglas(por_tema: dict) -> str:
    return "\n".join(f"[{tema}] {r['regla']} — ej.: {r['ejemplo']}" for tema, rs in por_tema.items() for r in rs)


def _guardar_en_memoria(por_tema: dict) -> None:
    memoria.borrar_video(PREFIJO + "canal")
    memoria.guardar_filas([{"video": PREFIJO + "canal", "inicio": 0.0, "funcion": "regla", "recurso": tema,
                            "frase": r["regla"], "por_que": f"{r['ejemplo']} · {r['cuando']}", "tono": ""}
                           for tema, rs in por_tema.items() for r in rs])


def _responder(pregunta: str, por_tema: dict) -> str:
    apoyo = memoria.buscar(pregunta, k=6)
    contexto = "\n".join(f"- {a['frase']} ({a['por_que']})" for a in apoyo)
    return ia.preguntar(f"Lo que recuerdas:\n{contexto}\n\nPregunta: {pregunta}\nResponde corto y con datos.",
                        papel="experto", sistema=SISTEMA_ESTUDIO + "\n" + _texto_reglas(por_tema)[:6000],
                        temperatura=0.2)


def _examen(por_tema: dict, aviso, preguntas: list[dict] | None = None, base: float = 65, ancho: float = 25) -> dict:
    if preguntas is None:
        trozos = [t for t in conocimiento.trozos_notas() if len(t.get("texto", "")) > 80]
        random.Random(7).shuffle(trozos)
        preguntas = []
        for t in trozos[:PREGUNTAS]:
            texto = f"({t.get('archivo', '')} · {t.get('seccion', '')}) {t['texto']}"
            q = ia.estructurado(PEDIDO_PREGUNTA.format(texto=texto), Pregunta, papel="rapido",
                                sistema=SISTEMA_ESTUDIO)
            preguntas.append({**json.loads(q.model_dump_json()), "fuente": t.get("archivo", ""), "texto": texto})
    for k, p in enumerate(preguntas):
        p["alumno"] = _responder(p["pregunta"], por_tema)
        j = ia.estructurado(PEDIDO_JUEZ.format(pregunta=p["pregunta"], correcta=p["respuesta"], alumno=p["alumno"]),
                            Juicio, papel="rapido", sistema=SISTEMA_ESTUDIO, temperatura=0.0)
        p["correcta"], p["falta"] = j.correcta, j.falta
        aviso(f"Examen: pregunta {k + 1} de {len(preguntas)}", base + ancho * (k + 1) / len(preguntas))
    nota = sum(p["correcta"] for p in preguntas) / max(1, len(preguntas))
    return {"nota": round(nota, 2), "aprobado": nota >= APRUEBA, "preguntas": preguntas}


def sistema_experto(por_tema: dict | None = None) -> str:
    por_tema = _reglas() if por_tema is None else por_tema
    from . import personaje
    return "\n\n".join(x for x in [
        SISTEMA_ESTUDIO,
        "GUÍA DEL CANAL:\n" + conocimiento.guia(),
        "REGLAS QUE APRENDISTE (con ejemplo):\n" + _texto_reglas(por_tema)[:9000],
        personaje.texto()] if x.strip())


def estudiar(aviso=None, forzar: bool = False) -> dict:
    """Todo el estudio. Devuelve el estado final."""
    externo = aviso or (lambda m, p: None)

    def av(m, p):
        externo(m, p)
        _estado(mensaje=m, progreso=round(p))
    h = huella()
    if not forzar and _estado().get("huella") == h and REGLAS.exists():
        return estado()
    _estado(trabajando=True, error=None, pausado=False, mensaje="Empezando a estudiar", progreso=1)
    try:
        conocimiento.sembrar()
        por_tema = _juntar(_leer_y_sacar_reglas(av), av)
        REGLAS.write_text(json.dumps({"por_tema": por_tema}, ensure_ascii=False, indent=1), encoding="utf-8")
        _guardar_en_memoria(por_tema)
        ex = _examen(por_tema, av)
        falladas = [p for p in ex["preguntas"] if not p["correcta"]]
        if falladas:  # lo que falló se vuelve a estudiar y se pregunta otra vez
            por_tema["refuerzo"] = [{"tema": "refuerzo", "regla": f"{p['pregunta']} → {p['respuesta']}",
                                     "ejemplo": p["texto"][:300], "cuando": "dato que había fallado",
                                     "fuente": p["fuente"]} for p in falladas]
            REGLAS.write_text(json.dumps({"por_tema": por_tema}, ensure_ascii=False, indent=1), encoding="utf-8")
            _guardar_en_memoria(por_tema)
            repaso = _examen(por_tema, av, [dict(p) for p in falladas], base=90, ancho=5)
            ex["repaso"] = {"nota": repaso["nota"], "preguntas": len(falladas)}
            ex["nota_final"] = round((len(ex["preguntas"]) - len(falladas) +
                                      sum(p["correcta"] for p in repaso["preguntas"])) / len(ex["preguntas"]), 2)
        else:
            ex["nota_final"] = ex["nota"]
        EXAMEN.write_text(json.dumps(ex, ensure_ascii=False, indent=1), encoding="utf-8")
        av("Creando su modelo propio en Ollama", 96)
        ia.crear_modelo(ia.MODELOS["experto"], ia.MODELOS["rapido"], sistema_experto(por_tema))
        _estado(huella=h, trabajando=False, mensaje="Estudio terminado", progreso=100)
    except Exception as e:
        if type(e).__name__ != "Cancelado":
            _estado(trabajando=False, error=str(e))
        raise
    return estado()


def sugerir(pregunta: str) -> str:
    """Pregunta libre al editor experto (ventana «Pregúntale»), con su memoria y sus reglas."""
    return _responder(pregunta, _reglas())
