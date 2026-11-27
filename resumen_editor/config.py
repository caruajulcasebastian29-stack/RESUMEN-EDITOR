"""Carga de los archivos de estilo que la app lee (estilo/*.json)."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CARPETA_ESTILO = RAIZ / "estilo"
CARPETA_RECURSOS = RAIZ / "recursos"


@lru_cache(maxsize=None)
def estilo(nombre: str) -> dict:
    return json.loads((CARPETA_ESTILO / f"{nombre}.json").read_text(encoding="utf-8"))


def preferencias() -> dict:
    return json.loads((CARPETA_ESTILO / "preferencias.json").read_text(encoding="utf-8"))


def guardar_preferencias(datos: dict) -> None:
    (CARPETA_ESTILO / "preferencias.json").write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")
