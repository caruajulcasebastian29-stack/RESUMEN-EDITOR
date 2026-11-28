"""Memoria de la app: lo aprendido de los videos de referencia, guardado para siempre en disco.

LanceDB guarda cada recurso aprendido (frase, función, recurso, por qué funciona, de qué video salió)
con su vector de significado. Al escribir un guion la app pregunta, por ejemplo,
«cómo meten un chiste cuando el villano gana» y recibe los ejemplos reales más parecidos.
"""
from __future__ import annotations

import os
from pathlib import Path

from . import ia

CARPETA = Path(os.environ.get("RESUMEN_EDITOR_DATOS", Path.home() / "Documents" / "Resumen Editor")) / "memoria"
TABLA = "ejemplos"


def _db():
    import lancedb
    CARPETA.mkdir(parents=True, exist_ok=True)
    return lancedb.connect(str(CARPETA))


def _texto(m: dict) -> str:
    return f"{m['funcion']} · {m['recurso']}: {m['frase']} — {m['por_que_funciona']}"


def guardar_video(video_id: str, narracion: dict) -> int:
    """Guarda (o reemplaza) todos los recursos aprendidos de un video."""
    filas = []
    for v in narracion.get("ventanas", []):
        for m in v.get("momentos", []):
            filas.append({"video": video_id, "inicio": float(m["inicio"]), "funcion": m["funcion"],
                          "recurso": m["recurso"], "frase": m["frase"], "por_que": m["por_que_funciona"],
                          "tono": v.get("tono", "")})
    g = narracion.get("gancho")
    if g:
        filas.append({"video": video_id, "inicio": 0.0, "funcion": "gancho", "recurso": g["tipo"],
                      "frase": g["frase"], "por_que": g["promesa"], "tono": ""})
    borrar_video(video_id)
    return guardar_filas(filas)


def _limpio(texto: str) -> str:
    return texto.replace("'", "")


def guardar_filas(filas: list[dict]) -> int:
    """Añade filas ya armadas (video, inicio, funcion, recurso, frase, por_que, tono)."""
    if not filas:
        return 0
    vecs = []
    for i in range(0, len(filas), 32):  # de a pocos: la tarjeta de 4 GB no aguanta cientos de golpe
        vecs += ia.vectores([_texto({**f, "por_que_funciona": f["por_que"]}) for f in filas[i:i + 32]])
    for f, v in zip(filas, vecs):
        f["vector"] = v
    db = _db()
    if TABLA in db.table_names():
        db.open_table(TABLA).add(filas)
    else:
        db.create_table(TABLA, filas)
    return len(filas)


def borrar_video(video_id: str) -> None:
    db = _db()
    if TABLA in db.table_names():
        db.open_table(TABLA).delete(f"video = '{_limpio(video_id)}'")


def hay_video(prefijo: str) -> bool:
    db = _db()
    if TABLA not in db.table_names():
        return False
    return db.open_table(TABLA).count_rows(f"video LIKE '{_limpio(prefijo)}%'") > 0


def buscar(consulta: str, k: int = 8, funcion: str | None = None) -> list[dict]:
    db = _db()
    if TABLA not in db.table_names():
        return []
    q = db.open_table(TABLA).search(ia.vectores([consulta])[0]).limit(k)
    if funcion:
        q = q.where(f"funcion = '{funcion}'", prefilter=True)
    return [{k2: r[k2] for k2 in ("video", "funcion", "recurso", "frase", "por_que", "tono")} for r in q.to_list()]


def cuantos() -> int:
    db = _db()
    return db.open_table(TABLA).count_rows() if TABLA in db.table_names() else 0
