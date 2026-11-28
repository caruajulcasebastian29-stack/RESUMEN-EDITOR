"""Actualizaciones sin reinstalar: la app se baja solo su código nuevo (unos pocos MB) desde GitHub.

Cada versión publicada trae dos archivos además del instalador completo:
  app.zip         las carpetas de la app (resumen_editor, interfaz, estilo, recursos) y su version.txt
  requisitos.txt  la huella de los paquetes de Python que necesita esa versión
Si la huella es la misma que la instalada, basta con app.zip. Si cambió (hace falta un paquete nuevo),
la app avisa que esa versión necesita el instalador completo.
Los proyectos, lo aprendido y la memoria están en Documentos/Resumen Editor y no se tocan nunca.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
import zipfile
from pathlib import Path

from .config import RAIZ

REPO = "caruajulcasebastian29-stack/RESUMEN-EDITOR"
API = f"https://api.github.com/repos/{REPO}/releases/latest"
DATOS = Path(os.environ.get("RESUMEN_EDITOR_DATOS", Path.home() / "Documents" / "Resumen Editor"))
CARPETAS = ("resumen_editor", "interfaz", "estilo", "recursos")
estado: dict = {"mensaje": "", "progreso": 0, "error": None, "listo": False}


def _leer(nombre: str, defecto: str = "") -> str:
    ruta = RAIZ / nombre
    return ruta.read_text(encoding="utf-8").strip() if ruta.exists() else defecto


def version_local() -> str:
    return _leer("version.txt", "0.0.0")


def _numeros(v: str) -> tuple[int, ...]:
    return tuple(int(x) for x in v.lstrip("v").split(".") if x.isdigit())


def _get(url: str, timeout: int = 20) -> bytes:
    cabeceras = {"User-Agent": "ResumenEditor"}
    if url.startswith("https://api.github.com"):
        cabeceras["Accept"] = "application/vnd.github+json"
    req = urllib.request.Request(url, headers=cabeceras)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def buscar() -> dict:
    """¿Hay una versión nueva? Devuelve qué tipo de actualización necesita."""
    local = version_local()
    try:
        rel = json.loads(_get(API))
    except Exception as e:
        return {"local": local, "hay": False, "error": f"No se pudo consultar GitHub: {e}"}
    remota = rel.get("tag_name", "v0").lstrip("v")
    assets = {a["name"]: a["browser_download_url"] for a in rel.get("assets", [])}
    datos = {"local": local, "remota": remota, "hay": _numeros(remota) > _numeros(local),
             "pagina": rel.get("html_url", f"https://github.com/{REPO}/releases/latest"), "rapida": False}
    if datos["hay"] and "app.zip" in assets and "requisitos.txt" in assets:
        try:
            datos["rapida"] = _get(assets["requisitos.txt"]).decode().strip() == _leer("requisitos.txt")
        except Exception:
            pass
    datos["app_zip"] = assets.get("app.zip")
    return datos


def _reiniciar() -> None:
    """Abre la app de nuevo cuando esta se haya cerrado, y cierra esta."""
    py = Path(sys.executable)
    pyw = py.with_name("pythonw.exe") if py.with_name("pythonw.exe").exists() else py
    codigo = ("import time, subprocess, sys; time.sleep(3); "
              f"subprocess.Popen([{str(pyw)!r}, '-m', 'resumen_editor.lanzador', '--sin-ventana'], cwd={str(RAIZ)!r})")
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "DETACHED_PROCESS", 0)
    subprocess.Popen([str(pyw), "-c", codigo], cwd=str(RAIZ), creationflags=flags, close_fds=True)
    time.sleep(0.5)
    os._exit(0)


def aplicar(url_zip: str) -> None:
    """Baja app.zip, reemplaza el código de la app y la reinicia. Corre en segundo plano."""
    def trabajo():
        try:
            carpeta = DATOS / "actualizacion"
            shutil.rmtree(carpeta, ignore_errors=True)
            carpeta.mkdir(parents=True)
            estado.update(mensaje="Descargando la actualización…", progreso=10, error=None, listo=False)
            zip_ruta = carpeta / "app.zip"
            zip_ruta.write_bytes(_get(url_zip, timeout=300))
            estado.update(mensaje="Revisando el paquete…", progreso=50)
            nuevo = carpeta / "nuevo"
            with zipfile.ZipFile(zip_ruta) as z:
                z.extractall(nuevo)
            if not (nuevo / "resumen_editor" / "servidor.py").exists():
                raise RuntimeError("El paquete descargado está incompleto; no se cambió nada.")
            # copia de seguridad del código actual, por si algo sale mal
            respaldo = carpeta / "respaldo"
            for c in CARPETAS:
                if (RAIZ / c).exists():
                    shutil.copytree(RAIZ / c, respaldo / c, dirs_exist_ok=True)
            estado.update(mensaje="Instalando…", progreso=70)
            for c in CARPETAS:
                if (nuevo / c).exists():
                    shutil.copytree(nuevo / c, RAIZ / c, dirs_exist_ok=True)
            for f in ("version.txt", "requisitos.txt"):
                if (nuevo / f).exists():
                    shutil.copy2(nuevo / f, RAIZ / f)
            estado.update(mensaje="Listo. La app se reinicia en unos segundos…", progreso=100, listo=True)
            threading.Timer(1.5, _reiniciar).start()
        except Exception as e:
            estado.update(error=f"No se pudo actualizar: {e}", progreso=0)
    threading.Thread(target=trabajo, daemon=True).start()
