"""Punto de entrada de la app instalada en Windows (lo abre el acceso directo, sin consola).

Prepara el entorno (FFmpeg, Rhubarb, carpetas de datos y modelos) y abre la ventana de la app
en el navegador. Si la app ya estaba abierta, solo vuelve a abrir la ventana.
"""
from __future__ import annotations

import os
import socket
import sys
import webbrowser
from pathlib import Path

PUERTO = 8765
RAIZ = Path(__file__).resolve().parents[1]          # carpeta de la app
BASE = RAIZ.parent                                   # carpeta de instalación


def _preparar() -> None:
    herramientas = [BASE / "ffmpeg" / "bin", BASE / "rhubarb"]
    os.environ["PATH"] = os.pathsep.join([str(h) for h in herramientas if h.exists()] + [os.environ.get("PATH", "")])
    rhubarb = BASE / "rhubarb" / "rhubarb.exe"
    if rhubarb.exists():
        os.environ.setdefault("RHUBARB", str(rhubarb))
    datos = Path(os.environ.get("RESUMEN_EDITOR_DATOS", Path.home() / "Documents" / "Resumen Editor"))
    datos.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("RESUMEN_EDITOR_DATOS", str(datos))
    os.environ.setdefault("RESUMEN_EDITOR_MODELOS", str(datos / "modelos"))
    if sys.stdout is None:  # pythonw no tiene consola: lo que se imprima va a un registro
        registro = open(datos / "registro.txt", "a", encoding="utf-8", buffering=1)
        sys.stdout = sys.stderr = registro


def _ya_abierta() -> bool:
    with socket.socket() as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", PUERTO)) == 0


def main() -> None:
    _preparar()
    if _ya_abierta():
        webbrowser.open(f"http://127.0.0.1:{PUERTO}")
        return
    sys.path.insert(0, str(RAIZ))
    from resumen_editor.servidor import abrir
    abrir(PUERTO)


if __name__ == "__main__":
    main()
