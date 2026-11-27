"""Ventana de la aplicación: servidor local + página en el navegador.

Al abrir el programa se levanta en http://127.0.0.1:8765 y se abre solo. No se usa consola.
"""
from __future__ import annotations

import json
import shutil
import threading
import webbrowser

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse

from . import proyecto as P
from .config import RAIZ

app = FastAPI(title="Resumen Editor")
INTERFAZ = RAIZ / "interfaz" / "index.html"
_abiertos: dict[str, P.Proyecto] = {}


def _p(nombre: str) -> P.Proyecto:
    carpeta = P.PROYECTOS / nombre
    if not carpeta.is_dir():
        raise HTTPException(404, "No existe ese proyecto")
    return _abiertos.setdefault(nombre, P.Proyecto(carpeta))


@app.get("/", response_class=HTMLResponse)
def inicio():
    return INTERFAZ.read_text(encoding="utf-8")


@app.get("/api/proyectos")
def proyectos():
    return P.listar()


@app.post("/api/proyectos")
async def nuevo(video: UploadFile = File(...)):
    temporal = P.DATOS / "subidas" / video.filename
    temporal.parent.mkdir(parents=True, exist_ok=True)
    with temporal.open("wb") as f:
        shutil.copyfileobj(video.file, f)
    p = P.Proyecto.crear(temporal)
    temporal.unlink(missing_ok=True)
    _abiertos[p.dir.name] = p
    p.correr_todo()
    return {"nombre": p.dir.name}


@app.get("/api/proyectos/{nombre}")
def estado(nombre: str):
    p = _p(nombre)
    mapa = p.leer("entender/mapa.json")
    return {"estado": p.estado(), "limpieza": p.leer("limpieza.json"), "guion": p.leer("guion.json"),
            "lotes": p.leer("lotes.json", []), "diagnostico": p.leer("entender/diagnostico.json"),
            "pelicula": (mapa or {}).get("pelicula"), "revision": p.leer("revision.json")}


@app.post("/api/proyectos/{nombre}/continuar")
def continuar(nombre: str):
    p = _p(nombre)
    p.guardar_estado(error=None)
    p.correr_todo()
    return {"ok": True}


@app.post("/api/proyectos/{nombre}/excluido/{i}")
def alternar_excluido(nombre: str, i: int):
    """Jhon desmarca (o vuelve a marcar) un tramo que la app creyó publicidad."""
    p = _p(nombre)
    limp = p.leer("limpieza.json")
    limp["excluidos"][i]["desmarcado"] = not limp["excluidos"][i].get("desmarcado", False)
    p.escribir("limpieza.json", limp)
    return limp


@app.post("/api/proyectos/{nombre}/lotes/{n}")
def marcar(nombre: str, n: int, ok: bool = Form(...), comentario: str = Form("")):
    _p(nombre).marcar_lote(n, ok, comentario)
    return {"ok": True}


@app.post("/api/proyectos/{nombre}/rehacer")
def rehacer(nombre: str):
    p = _p(nombre)

    def trabajo():
        try:
            p.rehacer_marcados()
        except Exception as e:
            p.guardar_estado(error=str(e))
    threading.Thread(target=trabajo, daemon=True).start()
    return {"ok": True}


@app.post("/api/proyectos/{nombre}/exportar")
def exportar(nombre: str, formato: str = Form("youtube"), partes: int = Form(1)):
    salidas = _p(nombre).exportar(formato, partes)
    return {"archivos": [str(s) for s in salidas]}


@app.get("/api/proyectos/{nombre}/archivo/{ruta:path}")
def archivo(nombre: str, ruta: str):
    p = _p(nombre)
    destino = (p.dir / ruta).resolve()
    if p.dir.resolve() not in destino.parents or not destino.exists():
        raise HTTPException(404)
    return FileResponse(destino)


@app.get("/api/ajustes")
def ver_ajustes():
    from .cerebro import ia
    a = P.ajustes()
    a["clave_gemini"] = "••••" + a["clave_gemini"][-4:] if a["clave_gemini"] else ""
    a["modelos"] = ia.MODELOS
    return a


@app.post("/api/ajustes")
def cambiar_ajustes(clave_gemini: str = Form(""), motor_voz: str = Form("generica"), acento: str = Form("peru"),
                    mostrar_mapache: bool = Form(False)):
    nuevos = {"motor_voz": motor_voz, "acento": acento, "mostrar_mapache": mostrar_mapache}
    if clave_gemini and not clave_gemini.startswith("••••"):
        nuevos["clave_gemini"] = clave_gemini.strip()
    P.guardar_ajustes(nuevos)
    return {"ok": True}


# ---------- salud del equipo ----------
@app.get("/api/salud")
def salud():
    from .cerebro import ia
    ok_ollama = ia.disponible()
    faltan = []
    if ok_ollama:
        hay = set(ia.instalados())
        faltan = [m for m in ia.MODELOS.values() if m not in hay and m + ":latest" not in hay]
    return {"ollama": ok_ollama, "modelos_faltantes": faltan, "ffmpeg": shutil.which("ffmpeg") is not None}


@app.post("/api/salud/descargar")
def descargar_modelos():
    from .cerebro import ia

    def trabajo():
        for m in ia.MODELOS.values():
            try:
                ia.descargar_modelo(m, aviso=lambda msg, p: _estado_ref(mensaje=msg, progreso=round(p)))
            except Exception as e:
                _estado_ref(error=f"No se pudo descargar {m}: {e}")
        _estado_ref(mensaje="Modelos listos", progreso=100)
    threading.Thread(target=trabajo, daemon=True).start()
    return {"ok": True}


# ---------- referencias: la app aprende de videos de otros canales ----------
def _estado_ref(**campos):
    from .cerebro import aprender
    ruta = aprender.FICHAS / "_estado.json"
    ruta.parent.mkdir(parents=True, exist_ok=True)
    e = json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else {}
    e.update(campos)
    ruta.write_text(json.dumps(e, ensure_ascii=False), encoding="utf-8")
    return e


@app.get("/api/referencias")
def referencias():
    from .cerebro import aprender
    fichas = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(aprender.FICHAS.glob("*/ficha.json"))]
    estado = _estado_ref()
    manual = json.loads(aprender.MANUAL.read_text(encoding="utf-8")) if aprender.MANUAL.exists() else {}
    return {"fichas": fichas, "manual": manual, "estado": estado}


@app.post("/api/referencias")
async def nueva_referencia(video: UploadFile = File(...)):
    from .cerebro import aprender
    destino = aprender.DATOS / "referencias_videos" / video.filename
    destino.parent.mkdir(parents=True, exist_ok=True)
    with destino.open("wb") as f:
        shutil.copyfileobj(video.file, f)

    def trabajo():
        try:
            _estado_ref(video=video.filename, error=None, mensaje="Empezando", progreso=0)
            aprender.aprender(destino, aviso=lambda m, p: _estado_ref(mensaje=m, progreso=round(p)))
            _estado_ref(mensaje=f"Aprendido: {video.filename}", progreso=100)
        except Exception as e:
            _estado_ref(error=str(e))
    threading.Thread(target=trabajo, daemon=True).start()
    return {"ok": True}


def abrir(puerto: int = 8765) -> None:
    import uvicorn
    threading.Timer(1.5, lambda: webbrowser.open(f"http://127.0.0.1:{puerto}")).start()
    uvicorn.run(app, host="127.0.0.1", port=puerto, log_level="warning")


if __name__ == "__main__":
    abrir()
