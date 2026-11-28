"""Complementos: herramientas nuevas que llegan con una actualización y se instalan solas.

La actualización rápida (botón «Actualizar ahora») solo copia los archivos de la app. Cuando una versión
nueva necesita una librería más (por ejemplo, el lector de texto en pantalla o Praat para la voz), se
anota en complementos.txt y la app la instala sola al abrirse, con su propio Python y sin ventanas negras.

De dónde se descargan, en este orden:
  1. Del paquete «ruedas» publicado en GitHub junto con la app (GitHub ya funciona en la PC de Jhon:
     de ahí bajan las actualizaciones). Se instala sin conectarse a ningún otro sitio.
  2. Si eso falla, de PyPI (el sitio normal de Python), que en algunas redes no resuelve.
Si falla todo, vuelve a intentarlo sola cada minuto y medio. Desde la ventana se puede reintentar o cancelar.
"""
from __future__ import annotations

import importlib.util
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

LISTA = Path(__file__).with_name("complementos.txt")
REPO = "caruajulcasebastian29-stack/RESUMEN-EDITOR"
RUEDAS = f"https://github.com/{REPO}/releases/download/complementos-1/ruedas-win-py312.zip"
DATOS = Path(os.environ.get("RESUMEN_EDITOR_DATOS", Path.home() / "Documents" / "Resumen Editor"))
ESPERA_REINTENTO_S = 90

_estado = {"instalando": False, "faltan": [], "error": None, "listo": False, "intentos": 0,
           "mensaje": "", "progreso": 0, "cancelado": False}
_ctl = {"t": 0.0, "proc": None, "parar": threading.Event()}


class _Cancelado(Exception):
    pass


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
    importlib.invalidate_caches()
    return [pip for pip, modulo in _pedidos() if importlib.util.find_spec(modulo) is None]


def _python() -> str:
    exe = Path(sys.executable)
    consola = exe.with_name("python.exe")  # pythonw no muestra la salida de pip
    return str(consola if exe.name.lower() == "pythonw.exe" and consola.exists() else exe)


def _aviso(mensaje: str, progreso: float) -> None:
    if _ctl["parar"].is_set():
        raise _Cancelado()
    _estado.update(mensaje=mensaje, progreso=round(progreso))


def _pip(*args: str) -> tuple[int, str]:
    """Corre pip sin ventana; se puede cancelar a la mitad."""
    if _ctl["parar"].is_set():
        raise _Cancelado()
    registro = DATOS / "complementos_pip.log"
    registro.parent.mkdir(parents=True, exist_ok=True)
    banderas = 0x08000000 if os.name == "nt" else 0  # CREATE_NO_WINDOW
    with registro.open("w", encoding="utf-8", errors="replace") as salida:
        p = subprocess.Popen([_python(), "-m", "pip", "install", "--no-warn-script-location",
                              "--disable-pip-version-check", *args],
                             stdout=salida, stderr=subprocess.STDOUT, creationflags=banderas)
        _ctl["proc"] = p
        inicio = time.time()
        while p.poll() is None:
            if _ctl["parar"].is_set() or time.time() - inicio > 1800:
                p.kill()
                p.wait()
                _ctl["proc"] = None
                raise _Cancelado()
            time.sleep(0.5)
    _ctl["proc"] = None
    if _ctl["parar"].is_set():  # lo mató «Cancelar» desde la ventana
        raise _Cancelado()
    return p.returncode, registro.read_text(encoding="utf-8", errors="replace")[-600:]


def _desde_github(pendientes: list[str]) -> tuple[bool, str]:
    carpeta = DATOS / "complementos"
    zip_ = carpeta / "ruedas.zip"
    ruedas = carpeta / "ruedas"
    carpeta.mkdir(parents=True, exist_ok=True)
    try:
        _aviso("Descargando las herramientas nuevas desde GitHub", 2)
        temporal = zip_.with_suffix(".parcial")
        req = urllib.request.Request(RUEDAS, headers={"User-Agent": "ResumenEditor"})
        with urllib.request.urlopen(req, timeout=60) as r, temporal.open("wb") as f:
            total = int(r.headers.get("Content-Length") or 0)
            bajado = 0
            while True:
                trozo = r.read(1 << 20)
                if not trozo:
                    break
                f.write(trozo)
                bajado += len(trozo)
                if total:
                    _aviso(f"Descargando las herramientas nuevas desde GitHub ({bajado >> 20} de {total >> 20} MB)",
                           2 + 68 * bajado / total)
        temporal.replace(zip_)
        if ruedas.exists():
            shutil.rmtree(ruedas, ignore_errors=True)
        with zipfile.ZipFile(zip_) as z:
            z.extractall(ruedas)
    except _Cancelado:
        raise
    except Exception as e:
        return False, f"No se pudo bajar de GitHub: {e}"
    _aviso("Instalando las herramientas nuevas", 75)
    codigo, salida = _pip("--no-index", "--find-links", str(ruedas), *pendientes)
    return codigo == 0, salida


def instalar() -> None:
    _ctl["t"] = time.time()
    _estado.update(intentos=_estado["intentos"] + 1, cancelado=False, error=None, progreso=1)
    pendientes = faltan()
    _estado["faltan"] = pendientes
    if not pendientes:
        _estado.update(listo=True, instalando=False, mensaje="Herramientas listas", progreso=100)
        return
    _estado["instalando"] = True
    try:
        ok, salida = _desde_github(pendientes) if os.name == "nt" else (False, "")
        if not ok:
            _aviso("Probando desde PyPI", 80)
            codigo, salida2 = _pip(*pendientes)
            ok, salida = codigo == 0, (salida + "\n" + salida2)[-600:]
        _estado["faltan"] = faltan()
        _estado["listo"] = not _estado["faltan"]
        if _estado["listo"]:
            _estado.update(mensaje="Herramientas listas", progreso=100)
        else:
            _estado["error"] = salida or "No se pudieron instalar."
    except _Cancelado:
        _estado.update(cancelado=True, mensaje="Instalación cancelada. Pulsa «Reintentar» cuando quieras.", progreso=0)
    except Exception as e:
        _estado["error"] = str(e)
    finally:
        _estado["instalando"] = False
        try:
            (DATOS / "complementos.json").write_text(json.dumps(_estado, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass


def en_segundo_plano() -> bool:
    if _estado["instalando"]:
        return False
    _estado["instalando"] = True  # se marca antes de lanzar, para no lanzar dos a la vez
    _ctl["parar"].clear()
    threading.Thread(target=instalar, daemon=True).start()
    return True


def cancelar() -> None:
    _ctl["parar"].set()
    p = _ctl["proc"]
    if p is not None and p.poll() is None:
        p.kill()


def estado() -> dict:
    """La ventana pregunta cada pocos segundos; si falló (y no lo canceló Jhon), se reintenta sola."""
    if (_estado["error"] and _estado["faltan"] and not _estado["instalando"] and not _estado["cancelado"]
            and time.time() - _ctl["t"] > ESPERA_REINTENTO_S):
        en_segundo_plano()
    return dict(_estado)
