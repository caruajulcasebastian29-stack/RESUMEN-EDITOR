"""Banco: prueba el cerebro completo con Ollama de verdad.

1. Estudio del conocimiento: reglas, examen, repaso y modelo propio «mapache-editor».
2. Personaje: la IA marca frases (escritas para la prueba, en el estilo de la rata) y arma la personalidad.
3. Aprender de un video: todas las capas (tomas, audio, música, sonidos, texto, efectos, encuadre,
   palabras, voz, ritmo, imagen, narración y la descripción tramo por tramo).
4. Preguntas libres al editor experto.
Todo lo que sale queda en salida/cerebro.
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, ".")
OUT = Path("salida/cerebro")
OUT.mkdir(parents=True, exist_ok=True)


def guardar(nombre, datos):
    (OUT / nombre).write_text(json.dumps(datos, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


def aviso(m, p):
    print(f"   [{p:5.1f}%] {m}", flush=True)


from resumen_editor.cerebro import aprender, estudio, ia, personaje  # noqa: E402

paso = sys.argv[1] if len(sys.argv) > 1 else "todo"

if paso in ("todo", "estudio"):
    print("== 1. Estudio del conocimiento", flush=True)
    t0 = time.time()
    e = estudio.estudiar(aviso=aviso, forzar=True)
    print(f"   tardó {time.time() - t0:.0f} s · reglas {e.get('reglas')} · examen {e.get('examen')}")
    print("   modelos en Ollama:", ia.instalados())
    guardar("estudio_estado.json", e)
    for f in ("reglas.json", "examen.json"):
        r = estudio.CARPETA / f
        if r.exists():
            (OUT / f).write_text(r.read_text(encoding="utf-8"), encoding="utf-8")
    print("   sistema del modelo propio:", len(estudio.sistema_experto()), "caracteres")

if paso in ("todo", "personaje"):
    print("== 2. Personaje", flush=True)
    # frases escritas para la prueba (no copiadas de ningún clip), con medidas parecidas a las reales
    frases = [
        {"inicio": 0.5, "fin": 2.0, "hablante": "voz_0", "texto": "¿Y tú dónde estabas metido, oe?", "tono_hz": 340,
         "rango_st": 12, "sobresale_db": 4, "palabras_s": 3.4, "entonacion": "sube_al_final", "sonidos": ["grito"]},
        {"inicio": 2.1, "fin": 5.5, "hablante": "voz_0", "texto": "¡Me estaban correteando con una escoba y tú paseando, sinvergüenza!",
         "tono_hz": 360, "rango_st": 17, "sobresale_db": 6, "palabras_s": 3.6, "entonacion": "sube_al_final", "sonidos": ["grito"]},
        {"inicio": 5.6, "fin": 7.0, "hablante": "voz_1", "texto": "Perdón, pues.", "tono_hz": 150, "rango_st": 3,
         "sobresale_db": -8, "palabras_s": 1.8, "entonacion": "plana", "sonidos": []},
        {"inicio": 7.2, "fin": 10.0, "hablante": "voz_0", "texto": "¿Perdón? ¡Casi me muero, carajo, y tú con tu perdón!",
         "tono_hz": 370, "rango_st": 19, "sobresale_db": 7, "palabras_s": 4.2, "entonacion": "sube_y_baja", "sonidos": ["grito"]},
        {"inicio": 10.2, "fin": 13.0, "hablante": "voz_0", "texto": "Seguro estabas chismeando con tus amiguitas y vainas.",
         "tono_hz": 330, "rango_st": 10, "sobresale_db": 3, "palabras_s": 3.9, "entonacion": "plana", "sonidos": []},
        {"inicio": 13.5, "fin": 16.0, "hablante": "voz_0", "texto": "Estoy hasta la pin— ya no aguanto, oe.",
         "tono_hz": 380, "rango_st": 20, "sobresale_db": 9, "palabras_s": 4.6, "entonacion": "sube_al_final", "sonidos": ["grito"]},
        {"inicio": 20.0, "fin": 24.0, "hablante": "voz_2", "texto": "Mira, causa, la cosa fue así nomás, tranquilo te cuento.",
         "tono_hz": 120, "rango_st": 6, "sobresale_db": -2, "palabras_s": 2.6, "entonacion": "baja_al_final", "sonidos": []},
        {"inicio": 24.5, "fin": 28.0, "hablante": "voz_2", "texto": "Y el tonto este se mete solito a la boca del lobo, ¿ya ves?",
         "tono_hz": 130, "rango_st": 8, "sobresale_db": 0, "palabras_s": 3.0, "entonacion": "sube_al_final", "sonidos": []},
    ]
    t0 = time.time()
    m = personaje.marcar(frases, "rabia")
    personaje.CARPETA.joinpath("prueba").mkdir(parents=True, exist_ok=True)
    (personaje.CARPETA / "prueba" / "lineas.json").write_text(json.dumps(
        {"video": "prueba", "archivo": "frases de prueba", "rol": "rabia", "lineas": m}, ensure_ascii=False), encoding="utf-8")
    for x in m:
        print(f"   {x['registro']:17} {','.join(x['recursos']):40} {x['texto']}")
    p = personaje.armar_perfil(aviso)
    print(f"   tardó {time.time() - t0:.0f} s")
    print(personaje.texto(p))
    guardar("personaje_perfil.json", p)

if paso in ("todo", "video"):
    print("== 3. Aprender de un video (todas las capas)", flush=True)
    v = Path(sys.argv[2] if len(sys.argv) > 2 else "/tmp/ref.mp4")
    t0 = time.time()
    f = aprender.aprender(v, aviso=aviso)
    print(f"   tardó {time.time() - t0:.0f} s")
    guardar("ficha.json", f)
    carpeta = aprender.FICHAS / aprender.ident(v)
    for n in ("comprension.json", "sonidos.json", "encuadre.json", "texto.json", "voz.json"):
        r = carpeta / n
        if r.exists():
            d = json.loads(r.read_text(encoding="utf-8"))
            if n == "sonidos.json":
                d.pop("por_segundo", None)
            guardar(n, d)
    print(json.dumps(f.get("comprension"), ensure_ascii=False, indent=1))

if paso in ("todo", "preguntas"):
    print("== 4. Preguntas al editor experto", flush=True)
    salida = []
    for q in ["¿Cómo debe empezar el gancho de un resumen y cuántos segundos dura?",
              "¿Cuándo debe gritar el mapache y cómo remata?",
              "¿Cada cuántos segundos se corta la imagen en el gancho y en el resto del video?",
              "¿Qué tarjetas de tiempo se usan y de qué color?"]:
        t0 = time.time()
        r = estudio.sugerir(q)
        print(f"   P: {q}\n   R ({time.time() - t0:.0f} s): {r}\n")
        salida.append({"pregunta": q, "respuesta": r})
    guardar("preguntas.json", salida)
print("== cerebro listo")
