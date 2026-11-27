"""Conexión con Ollama: el cerebro local de la app.

Todo pedido al modelo pasa por aquí. Las respuestas que el programa necesita leer se piden con
un esquema JSON fijo (Ollama «structured outputs») y se validan con pydantic; si el modelo
devuelve algo que no cumple, se reintenta con el error a la vista.

Los modelos se cargan de uno en uno: en una tarjeta de 4 GB no caben dos a la vez.
"""
from __future__ import annotations

import base64
import json
import re
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Type, TypeVar

from pydantic import BaseModel, ValidationError

URL = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
if not URL.startswith("http"):
    URL = "http://" + URL

# Modelos por defecto (se cambian en Ajustes). Elegidos para una RTX 3050 de 4 GB.
MODELOS = {
    "vision": os.environ.get("RE_MODELO_VISION", "qwen3-vl:4b"),
    "rapido": os.environ.get("RE_MODELO_RAPIDO", "qwen3:4b-instruct"),
    "escritor": os.environ.get("RE_MODELO_ESCRITOR", "qwen3.5:9b"),
    "embeddings": os.environ.get("RE_MODELO_EMBED", "embeddinggemma"),
}

M = TypeVar("M", bound=BaseModel)


class ErrorIA(RuntimeError):
    pass


def _post(ruta: str, datos: dict, espera: float = 1800) -> dict:
    req = urllib.request.Request(URL + ruta, data=json.dumps(datos).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=espera) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise ErrorIA(f"Ollama respondió {e.code}: {e.read()[:300]!r}") from e
    except urllib.error.URLError as e:
        raise ErrorIA("No se pudo hablar con Ollama. ¿Está abierto?") from e


def disponible() -> bool:
    try:
        with urllib.request.urlopen(URL + "/api/version", timeout=3):
            return True
    except Exception:
        return False


def instalados() -> list[str]:
    with urllib.request.urlopen(URL + "/api/tags", timeout=10) as r:
        return [m["name"] for m in json.loads(r.read())["models"]]


def descargar_modelo(nombre: str, aviso=None) -> None:
    """Descarga un modelo si falta, informando el avance."""
    base = nombre if ":" in nombre else nombre + ":latest"
    if base in instalados():
        return
    req = urllib.request.Request(URL + "/api/pull", data=json.dumps({"model": nombre}).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=None) as r:
        for linea in r:
            d = json.loads(linea)
            if aviso and d.get("total"):
                aviso(f"Descargando {nombre}", 100 * d.get("completed", 0) / d["total"])
            if d.get("error"):
                raise ErrorIA(d["error"])


def liberar(papel: str) -> None:
    """Saca el modelo de la memoria de la tarjeta para dejar sitio al siguiente."""
    try:
        _post("/api/generate", {"model": MODELOS[papel], "keep_alive": 0}, espera=60)
    except ErrorIA:
        pass


def _limpiar(texto: str) -> str:
    """Quita el razonamiento interno que algunos modelos escriben aunque no se les pida."""
    texto = re.sub(r"<think>.*?</think>", "", texto, flags=re.S)
    if "</think>" in texto:
        texto = texto.split("</think>", 1)[1]
    return texto.strip()


def _generar(datos: dict) -> str:
    """Llama a /api/generate. Si el modelo no admite la opción de razonamiento, la quita y repite."""
    try:
        r = _post("/api/generate", datos)
    except ErrorIA as e:
        if "think" not in str(e).lower() or "think" not in datos:
            raise
        datos = {k: v for k, v in datos.items() if k != "think"}
        r = _post("/api/generate", datos)
    return _limpiar(r["response"])


def _imagen(ruta: Path | str) -> str:
    return base64.b64encode(Path(ruta).read_bytes()).decode()


def preguntar(prompt: str, *, papel: str = "rapido", sistema: str = "", imagenes=None,
              temperatura: float = 0.4, contexto: int = 8192, pensar: bool = False) -> str:
    """Respuesta libre en texto."""
    datos = {"model": MODELOS[papel], "prompt": prompt, "system": sistema, "stream": False,
             "think": pensar, "keep_alive": "10m",
             "options": {"temperature": temperatura, "num_ctx": contexto}}
    if imagenes:
        datos["images"] = [_imagen(i) for i in imagenes]
    return _generar(datos)


def estructurado(prompt: str, esquema: Type[M], *, papel: str = "rapido", sistema: str = "",
                 imagenes=None, temperatura: float = 0.2, contexto: int = 8192,
                 intentos: int = 3) -> M:
    """Respuesta que cumple un esquema pydantic. Reintenta mostrando el error al modelo."""
    nota = ""
    ultimo = None
    for _ in range(intentos):
        datos = {"model": MODELOS[papel], "prompt": prompt + nota, "system": sistema,
                 "stream": False, "think": False, "keep_alive": "10m",
                 "format": esquema.model_json_schema(),
                 "options": {"temperature": temperatura, "num_ctx": contexto}}
        if imagenes:
            datos["images"] = [_imagen(i) for i in imagenes]
        texto = _generar(datos)
        try:
            return esquema.model_validate_json(texto)
        except ValidationError as e:
            ultimo = e
            nota = ("\n\nTu respuesta anterior no cumplía el formato pedido. Error: "
                    f"{str(e)[:400]}\nResponde otra vez, solo con el JSON correcto.")
            temperatura = max(0.05, temperatura - 0.1)
    raise ErrorIA(f"El modelo no devolvió un JSON válido: {ultimo}")


def vectores(textos: list[str]) -> list[list[float]]:
    """Embeddings para la memoria."""
    salida: list[list[float]] = []
    for i in range(0, len(textos), 32):
        r = _post("/api/embed", {"model": MODELOS["embeddings"], "input": textos[i:i + 32]})
        salida += r["embeddings"]
    return salida


def cronometrar(funcion, *a, **k):
    t = time.time()
    r = funcion(*a, **k)
    return r, time.time() - t
