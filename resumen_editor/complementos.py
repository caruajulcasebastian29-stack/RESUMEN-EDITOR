"""Complementos: herramientas nuevas que llegan con una actualización y se instalan solas.

La actualización rápida (botón «Actualizar ahora») solo copia los archivos de la app. Cuando una versión
nueva necesita una librería más (por ejemplo, el lector de texto en pantalla o Praat para la voz), se
anota en complementos.txt y la app la instala sola al abrirse, con su propio Python y sin ventanas negras.
Mientras se instala, las funciones que la necesitan esperan o usan un plan B.
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

LISTA = Path(__file__).with_name("complementos.txt")
_estado = {"instalando": False, "faltan": [], "error": None, "listo": False, "intentos": 0}
_ultimo = {"t": 0.0}
ESPERA_REINTENTO_S = 90  # si falla (por ejemplo, internet todavía no conectado al reiniciar), vuelve a probar sola


def _pedidos() -> list[tuple[str, str]]:
    """(paquete de pip, nombre con que se importa)."""
    salida = []
    if LISTA.exists():
        for linea in LISTA.read_text(encoding="utf-8").splitlines():
            linea = linea.split("#")[0].strip()
            if linea:
                pip, _, modulo = linea.partition(" ")
                salida.append((pip, modulo.strip() or pip))
    return salida


def faltan() -> list[str]:
    return [pip for pip, modulo in _pedidos() if importlib.util.find_spec(modulo) is None]


def _python() -> str:
    exe = Path(sys.executable)
    consola = exe.with_name("python.exe")  # pythonw no muestra la salida de pip
    return str(consola if exe.name.lower() == "pythonw.exe" and consola.exists() else exe)


def instalar() -> None:
    _ultimo["t"] = time.time()
    _estado["intentos"] += 1
    pendientes = faltan()
    _estado.update(faltan=pendientes, error=None)
    if not pendientes:
        _estado.update(listo=True, instalando=False)
        return
    _estado["instalando"] = True
    banderas = 0x08000000 if os.name == "nt" else 0  # CREATE_NO_WINDOW
    try:
        r = subprocess.run([_python(), "-m", "pip", "install", "--no-warn-script-location", "--disable-pip-version-check",
                            *pendientes], capture_output=True, text=True, creationflags=banderas, timeout=1800)
        if r.returncode != 0:
            _estado["error"] = (r.stderr or r.stdout)[-600:]
        importlib.invalidate_caches()
        _estado["faltan"] = faltan()
        _estado["listo"] = not _estado["faltan"]
    except Exception as e:
        _estado["error"] = str(e)
    finally:
        _estado["instalando"] = False
        try:
            datos = Path(os.environ.get("RESUMEN_EDITOR_DATOS", Path.home() / "Documents" / "Resumen Editor"))
            (datos / "complementos.json").write_text(json.dumps(_estado, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass


def en_segundo_plano() -> None:
    if _estado["instalando"]:
        return
    _estado["instalando"] = True  # se marca antes de lanzar, para no lanzar dos a la vez
    threading.Thread(target=instalar, daemon=True).start()


def estado() -> dict:
    """La ventana pregunta cada 30 s; si la última vez falló, se reintenta sola cada minuto y medio."""
    if (_estado["error"] and _estado["faltan"] and not _estado["instalando"]
            and time.time() - _ultimo["t"] > ESPERA_REINTENTO_S):
        en_segundo_plano()
    return dict(_estado)
