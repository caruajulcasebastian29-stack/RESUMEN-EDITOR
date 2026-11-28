"""Capa · Sonidos: qué se oye en cada segundo (risas, gritos, golpes, disparos, y el ánimo de la música).

Usa un modelo gratuito de etiquetado de audio (CED, entrenado con AudioSet: 527 clases de sonido) que
corre en el procesador con sherpa-onnx. Se escucha la mezcla original de a ventanas de 2 s que avanzan
1 s, y de cada ventana quedan las etiquetas con probabilidad alta, agrupadas en nombres en español.

Sirve para dos cosas:
  - en los videos de referencia: cuántos efectos de sonido, risas o gritos pone el editor y dónde,
    y qué ánimo tiene la música en cada parte (graciosa, triste, de miedo, de tensión…);
  - en el personaje: cuándo grita, cuándo se ríe, cuándo llora de mentira.
"""
from __future__ import annotations

import json
import subprocess
from collections import Counter
from functools import lru_cache
from pathlib import Path

import numpy as np

from . import modelos

SR = 16000
VENTANA_S = 2.0
PASO_S = 1.0
MINIMO = 0.15         # efectos y gritos
MINIMO_ANIMO = 0.02   # el ánimo de la música sale con probabilidades bajas; se toma el mayor

# etiqueta de AudioSet -> grupo en español
GRUPOS = {
    "grito": ["Shout", "Yell", "Screaming", "Battle cry", "Children shouting", "Whoop"],
    "risa": ["Laughter", "Belly laugh", "Giggle", "Chuckle, chortle", "Snicker", "Baby laughter"],
    "llanto": ["Crying, sobbing", "Whimper", "Wail, moan", "Baby cry, infant cry"],
    "suspiro_o_queja": ["Sigh", "Groan", "Grunt", "Gasp"],
    "golpe": ["Slap, smack", "Punch", "Thump, thud", "Smash, crash", "Whack, thwack", "Bang"],
    "disparo_o_explosion": ["Gunshot, gunfire", "Explosion", "Machine gun", "Burst, pop", "Boom"],
    "efecto_comico": ["Boing", "Whoosh, swoosh, swish", "Cartoon", "Squeak", "Zing", "Honk",
                      "Slide whistle", "Sound effect", "Clang", "Ding", "Bell"],
    "aplausos_o_publico": ["Applause", "Cheering", "Crowd", "Hubbub, speech noise, speech babble"],
    "sirena_o_alarma": ["Siren", "Alarm", "Police car (siren)", "Ambulance (siren)", "Buzzer"],
    "pasos_puerta": ["Walk, footsteps", "Door", "Knock", "Slam"],
    "vidrio": ["Glass", "Shatter", "Breaking"],
    "animal": ["Animal", "Dog", "Cat", "Bird", "Roar", "Growling"],
    "auto": ["Vehicle", "Car", "Engine", "Skidding", "Tire squeal", "Car alarm"],
}
ANIMO_MUSICA = {
    "Funny music": "graciosa", "Happy music": "alegre", "Sad music": "triste", "Tender music": "tierna",
    "Exciting music": "emocionante", "Angry music": "de rabia", "Scary music": "de miedo",
}
GENERO_MUSICA = {
    "Soundtrack music": "de película", "Background music": "de fondo", "Theme music": "tema",
    "Video game music": "de videojuego", "Electronic music": "electrónica", "Hip hop music": "hip hop",
    "Music of Latin America": "latina", "Salsa music": "salsa",
}
_A_GRUPO = {e: g for g, es in GRUPOS.items() for e in es}
_HABLA = ("Speech", "Male speech, man speaking", "Female speech, woman speaking", "Conversation",
          "Narration, monologue")


@lru_cache(maxsize=1)
def _etiquetador():
    import sherpa_onnx
    carpeta = modelos.ruta("sonidos")
    cfg = sherpa_onnx.AudioTaggingConfig(
        model=sherpa_onnx.AudioTaggingModelConfig(ced=str(carpeta / "model.int8.onnx"), num_threads=2),
        labels=str(carpeta / "class_labels_indices.csv"), top_k=40)
    return sherpa_onnx.AudioTagging(cfg)


def _leer(ruta: Path) -> np.ndarray:
    crudo = subprocess.run(["ffmpeg", "-v", "error", "-i", str(ruta), "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
                           capture_output=True, check=True).stdout
    return np.frombuffer(crudo, dtype=np.float32)


def escuchar(ruta: Path, aviso=None) -> list[dict]:
    """Etiquetas por segundo: [{"t": 12.0, "grupos": {"grito": 0.61}, "musica": "triste", "habla": 0.9}]."""
    a = _leer(ruta)
    tag = _etiquetador()
    n_v, n_p = int(VENTANA_S * SR), int(PASO_S * SR)
    salida = []
    total = max(1, (len(a) - n_v) // n_p + 1)
    for k, i in enumerate(range(0, max(1, len(a) - n_v + 1), n_p)):
        trozo = a[i:i + n_v]
        if len(trozo) < SR // 2 or float(np.abs(trozo).max()) < 1e-3:
            salida.append({"t": round(i / SR, 1), "grupos": {}, "musica": None, "habla": 0.0})
            continue
        s = tag.create_stream()
        s.accept_waveform(SR, trozo)
        grupos, musica, genero, habla = {}, None, None, 0.0
        for e in tag.compute(s, 40):
            if e.name in ANIMO_MUSICA and musica is None and e.prob >= MINIMO_ANIMO:
                musica = ANIMO_MUSICA[e.name]
            if e.name in GENERO_MUSICA and genero is None and e.prob >= MINIMO_ANIMO:
                genero = GENERO_MUSICA[e.name]
            if e.prob < MINIMO:
                continue
            g = _A_GRUPO.get(e.name)
            if g:
                grupos[g] = max(grupos.get(g, 0), round(float(e.prob), 2))
            if e.name in _HABLA:
                habla = max(habla, round(float(e.prob), 2))
        salida.append({"t": round(i / SR, 1), "grupos": grupos, "musica": musica, "genero": genero, "habla": habla})
        if aviso and k % 60 == 0:
            aviso("Reconociendo sonidos", 100 * k / total)
    return salida


def eventos(por_segundo: list[dict]) -> list[dict]:
    """Une segundos seguidos del mismo grupo en un solo evento."""
    salida, abiertos = [], {}
    for s in por_segundo:
        for g in list(abiertos):
            if g not in s["grupos"]:
                salida.append(abiertos.pop(g))
        for g, p in s["grupos"].items():
            if g in abiertos:
                abiertos[g]["fin"] = s["t"] + VENTANA_S
                abiertos[g]["fuerza"] = max(abiertos[g]["fuerza"], p)
            else:
                abiertos[g] = {"tipo": g, "inicio": s["t"], "fin": s["t"] + VENTANA_S, "fuerza": p}
    salida += abiertos.values()
    return sorted(salida, key=lambda e: e["inicio"])


def analizar(video: Path, carpeta: Path, tomas: list[dict], dur: float, aviso=None) -> dict:
    """Escucha por separado el fondo (música y efectos, sin la voz) y la voz: en la mezcla la voz tapa todo."""
    destino = carpeta / "sonidos.json"
    if destino.exists():
        return json.loads(destino.read_text(encoding="utf-8"))
    fondo = carpeta / "musica.wav" if (carpeta / "musica.wav").exists() else video
    por_segundo = escuchar(fondo, (lambda m, p: aviso(m, p * 0.6)) if aviso else None)
    if (carpeta / "voz.wav").exists():  # gritos, risas y llanto se oyen en la voz
        voz = escuchar(carpeta / "voz.wav", (lambda m, p: aviso(m, 60 + p * 0.4)) if aviso else None)
        for s, v in zip(por_segundo, voz):
            for g in ("grito", "risa", "llanto", "suspiro_o_queja"):
                s["grupos"].pop(g, None)
                if g in v["grupos"]:
                    s["grupos"][g] = v["grupos"][g]
            s["habla"] = v["habla"]
    ev = eventos(por_segundo)
    cortes = np.array([t["inicio"] for t in tomas[1:]]) if len(tomas) > 1 else np.array([])
    for e in ev:
        e["en_corte"] = bool(len(cortes) and float(np.min(np.abs(cortes - e["inicio"]))) < 1.0)
    datos = {"por_segundo": por_segundo, "eventos": ev, "resumen": resumen(por_segundo, ev, dur)}
    destino.write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")
    return datos


def resumen(por_segundo: list[dict], ev: list[dict], dur: float) -> dict:
    minutos = max(dur / 60, 1e-6)
    cuenta = Counter(e["tipo"] for e in ev)
    animos = Counter(s["musica"] for s in por_segundo if s.get("musica"))
    tot = sum(animos.values()) or 1
    generos = Counter(s["genero"] for s in por_segundo if s.get("genero"))
    tot_g = sum(generos.values()) or 1
    con_voz = [s for s in por_segundo if s.get("habla", 0) >= 0.4]
    return {"por_minuto": {g: round(n / minutos, 2) for g, n in cuenta.most_common()},
            "en_corte": {g: round(sum(e["en_corte"] for e in ev if e["tipo"] == g) / n, 2)
                         for g, n in cuenta.items()},
            "animo_musica": {a: round(n / tot, 2) for a, n in animos.most_common(6)},
            "genero_musica": {a: round(n / tot_g, 2) for a, n in generos.most_common(4)},
            "tiempo_con_voz": round(len(con_voz) / max(1, len(por_segundo)), 2)}
