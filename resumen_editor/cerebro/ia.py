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
    # modelo propio que crea la app después de estudiar el conocimiento del canal (ver estudio.py)
    "experto": os.environ.get("RE_MODELO_EXPERTO", "mapache-editor"),
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
        _post("/api/generate", {"model": nombre(papel), "keep_alive": 0}, espera=60)
    except ErrorIA:
        pass


_hay_experto: list[bool] = []


def nombre(papel: str) -> str:
    """El modelo que corresponde a un papel. «experto» usa el rápido mientras no se haya creado."""
    if papel == "experto":
        if not _hay_experto:
            try:
                _hay_experto.append(any(m.split(":")[0] == MODELOS["experto"] for m in instalados()))
            except Exception:
                return MODELOS["rapido"]
        return MODELOS["experto"] if _hay_experto[0] else MODELOS["rapido"]
    return MODELOS[papel]


def crear_modelo(nuevo: str, base: str, sistema: str, temperatura: float = 0.4) -> None:
    """Crea en Ollama un modelo propio: el modelo base con el conocimiento del canal ya puesto."""
    try:
        _post("/api/create", {"model": nuevo, "from": base, "system": sistema, "stream": False,
                              "parameters": {"temperature": temperatura, "num_ctx": 8192}}, espera=600)
    except ErrorIA:  # versiones viejas de Ollama solo aceptan un Modelfile
        comillas = chr(34) * 3
        texto = sistema.replace(comillas, "'")
        modelfile = (f"FROM {base}\nPARAMETER temperature {temperatura}\nPARAMETER num_ctx 8192\n"
                     f"SYSTEM {comillas}{texto}{comillas}")
        _post("/api/create", {"name": nuevo, "stream": False, "modelfile": modelfile}, espera=600)
    _hay_experto.clear()


def _con_experto(papel: str, prompt: str, sistema: str) -> tuple[str, str]:
    """El modelo propio trae su conocimiento en sus instrucciones de fábrica (SYSTEM). Si el pedido manda otro
    «system», Ollama lo reemplaza; por eso, con el experto, las instrucciones del pedido van dentro del texto."""
    if papel == "experto" and sistema and nombre(papel) == MODELOS["experto"]:
        return f"Instrucciones para esta tarea:\n{sistema}\n\n{prompt}", ""
    return prompt, sistema


def _limpiar(texto: str) -> str:
    """Quita el razonamiento interno que algunos modelos escriben aunque no se les pida."""
    texto = re.sub(r"<think>.*?</think>", "", texto, flags=re.S)
    if "</think>" in texto:
        texto = texto.split("</think>", 1)[1]
    return texto.strip()


def _generar(datos: dict, espera: float = 1800) -> str:
    """Llama a /api/generate. Si el modelo no admite la opción de razonamiento, la quita y repite."""
    try:
        r = _post("/api/generate", datos, espera)
    except ErrorIA as e:
        if "think" not in str(e).lower() or "think" not in datos:
            raise
        datos = {k: v for k, v in datos.items() if k != "think"}
        r = _post("/api/generate", datos, espera)
    return _limpiar(r["response"])


def _imagen(ruta: Path | str) -> str:
    return base64.b64encode(Path(ruta).read_bytes()).decode()


def preguntar(prompt: str, *, papel: str = "rapido", sistema: str = "", imagenes=None,
              temperatura: float = 0.4, contexto: int = 8192, pensar: bool = False,
              maximo: int = 4096, espera: float = 1800) -> str:
    """Respuesta libre en texto. `maximo`: tope de tokens (evita que el modelo se quede repitiendo sin fin)."""
    prompt, sistema = _con_experto(papel, prompt, sistema)
    datos = {"model": nombre(papel), "prompt": prompt, "system": sistema, "stream": False,
             "think": pensar, "keep_alive": "10m",
             "options": {"temperature": temperatura, "num_ctx": contexto, "num_predict": maximo,
                         "repeat_penalty": 1.1}}
    if imagenes:
        datos["images"] = [_imagen(i) for i in imagenes]
    return _generar(datos, espera)


def estructurado(prompt: str, esquema: Type[M], *, papel: str = "rapido", sistema: str = "",
                 imagenes=None, temperatura: float = 0.2, contexto: int = 8192,
                 intentos: int = 3, maximo: int = 6000, espera: float = 1800) -> M:
    """Respuesta que cumple un esquema pydantic. Reintenta mostrando el error al modelo."""
    nota = ""
    ultimo = None
    prompt, sistema = _con_experto(papel, prompt, sistema)
    for _ in range(intentos):
        datos = {"model": nombre(papel), "prompt": prompt + nota, "system": sistema,
                 "stream": False, "think": False, "keep_alive": "10m",
                 "format": esquema.model_json_schema(),
                 "options": {"temperature": temperatura, "num_ctx": contexto, "num_predict": maximo,
                             "repeat_penalty": 1.1}}
        if imagenes:
            datos["images"] = [_imagen(i) for i in imagenes]
        try:
            texto = _generar(datos, espera)
        except (TimeoutError, OSError) as e:  # se colgó (suele ser un bucle repitiendo texto): otro intento
            ultimo = e
            temperatura = max(0.05, temperatura - 0.1) + 0.2
            continue
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
