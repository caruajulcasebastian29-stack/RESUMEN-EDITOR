"""Guion del mapache: frases con su tramo de imagen de origen y sus marcas.

Formato en disco (guion.json):
{
  "titulo": "...",
  "frases": [
    {"id": 1, "texto": "Texto con [marcas]", "fuente": [inicio_s, fin_s]}
  ]
}
"fuente" es el tramo del video original cuyas imágenes ilustran la frase.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

MARCA = re.compile(r"\[(\/?\w+)(?::\s*([^\]]*))?\]")


@dataclass
class Frase:
    id: int
    texto: str                     # con marcas, tal como lo escribió el guionista
    fuente: tuple[float, float]
    hablado: str = ""              # sin marcas: lo que dice la voz
    emocion: str = "tranquilo"
    rata: bool = False
    tarjeta: str | None = None
    lugar: str | None = None
    rotulo: str | None = None
    censura: bool = False
    gesto: str | None = None
    groseria: str | None = None
    pausa: bool = False
    marcas: list[str] = field(default_factory=list)
    fuentes: list | None = None    # varios tramos de origen (el gancho mezcla momentos de toda la película)
    velocidad: str = "normal"      # lenta · normal · rapida (lo decide el guionista)


def interpretar(id_: int, texto: str, fuente, en_rata: bool) -> tuple[Frase, bool]:
    f = Frase(id=id_, texto=texto, fuente=(float(fuente[0]), float(fuente[1])))
    for m in MARCA.finditer(texto):
        nombre, valor = m.group(1).lower(), (m.group(2) or "").strip()
        f.marcas.append(nombre)
        if nombre == "rata":
            en_rata = True
        elif nombre == "/rata":
            en_rata = False
            f.rata = True  # la frase que cierra el modo rata también va en rata
        elif nombre == "tarjeta":
            f.tarjeta = valor
        elif nombre == "lugar":
            f.lugar = valor
        elif nombre == "rotulo":
            f.rotulo = valor
        elif nombre == "censura":
            f.censura = True
        elif nombre == "gesto":
            f.gesto = valor or "burla"
        elif nombre == "groseria":
            f.groseria = valor
        elif nombre == "pausa":
            f.pausa = True
    f.rata = f.rata or en_rata
    # Lo hablado: se quitan las marcas, pero la grosería cortada sí se dice (hasta el corte).
    hablado = MARCA.sub(lambda m: (m.group(2) or "").rstrip("—-").strip() if m.group(1).lower() == "groseria" else "", texto)
    f.hablado = re.sub(r"\s+", " ", hablado).strip()
    if f.rata:
        f.emocion = "furioso"
        f.gesto = f.gesto or "furioso"
    elif f.gesto:
        f.emocion = f.gesto
    if f.groseria:
        f.gesto = "groseria"
    return f, en_rata


def cargar(ruta: Path) -> tuple[str, list[Frase]]:
    datos = json.loads(Path(ruta).read_text(encoding="utf-8"))
    frases, en_rata = [], False
    for i, fr in enumerate(datos["frases"], 1):
        f, en_rata = interpretar(fr.get("id", i), fr["texto"], fr["fuente"], en_rata)
        f.fuentes = fr.get("fuentes")
        f.velocidad = fr.get("velocidad", "normal")
        if fr.get("tono") and not f.rata and not f.groseria:
            f.emocion = fr["tono"]
        frases.append(f)
    return datos.get("titulo", ""), frases


def revisar(frases: list[Frase], dur_estimada_s: float) -> list[str]:
    """Comprueba las reglas del narrador; devuelve los avisos (vacío = todo bien)."""
    from .config import estilo
    cfg = estilo("narrador")
    avisos = []
    bloques_rata = sum(1 for a, b in zip([False] + [f.rata for f in frases], [f.rata for f in frases]) if b and not a)
    minutos = max(dur_estimada_s / 60, 1)
    maximo = cfg["registros"]["rata"]["por_video"]["max"] * max(1, minutos / 20)
    if bloques_rata > maximo:
        avisos.append(f"Hay {bloques_rata} arranques de rabia; el máximo para este largo es {maximo:.0f}.")
    groserias = [f.id for f in frases if f.groseria]
    if len(groserias) > max(1, minutos * 60 / cfg["groserias"]["minimo_segundos_entre"]) + 0.5:
        avisos.append(f"Demasiadas groserías ({len(groserias)}) para {minutos:.0f} min.")
    for f in frases:
        for prohibida in ("y es aquí donde todo cambia", "se menciona que"):
            if prohibida in f.hablado.lower():
                avisos.append(f"Frase {f.id}: muletilla prohibida «{prohibida}».")
    return avisos
