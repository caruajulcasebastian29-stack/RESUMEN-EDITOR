"""Ventana de la aplicación: servidor local + página en el navegador.

Al abrir el programa se levanta en http://127.0.0.1:8765 y se abre solo. No se usa consola.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path
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
    e = p.estado()
    e["interrumpido"] = (not p.trabajando and not e.get("error") and not e.get("detenido")
                         and e.get("paso") not in ("lotes", "creado") and (e.get("progreso") or 0) < 100)
    return {"estado": e, "trabajando": p.trabajando, "limpieza": p.leer("limpieza.json"), "guion": p.leer("guion.json"),
            "lotes": p.leer("lotes.json", []), "diagnostico": p.leer("entender/diagnostico.json"),
            "pelicula": (mapa or {}).get("pelicula"), "revision": p.leer("revision.json")}


@app.post("/api/proyectos/{nombre}/continuar")
def continuar(nombre: str):
    p = _p(nombre)
    p.guardar_estado(error=None, detenido=False)
    p.correr_todo()
    return {"ok": True}


@app.post("/api/proyectos/{nombre}/pausar")
@app.post("/api/proyectos/{nombre}/detener")
def detener(nombre: str):
    _p(nombre).detener()
    return {"ok": True}


@app.delete("/api/proyectos/{nombre}")
def eliminar(nombre: str):
    p = _p(nombre)
    try:
        p.eliminar()
    except RuntimeError as e:
        raise HTTPException(409, str(e))
    _abiertos.pop(nombre, None)
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

    if p.trabajando:
        raise HTTPException(409, "El proyecto ya está trabajando")
    p._parar.clear()

    def trabajo():
        try:
            p.rehacer_marcados()
        except P.Cancelado:
            p.guardar_estado(mensaje="Detenido.", detenido=True)
        except Exception as e:
            p.guardar_estado(error=str(e))
    p._hilo = threading.Thread(target=trabajo, daemon=True)
    p._hilo.start()
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
        faltan = [m for k, m in ia.MODELOS.items() if k != "experto" and m not in hay and m + ":latest" not in hay]
    from . import complementos
    return {"ollama": ok_ollama, "modelos_faltantes": faltan, "ffmpeg": shutil.which("ffmpeg") is not None,
            "complementos": complementos.estado(),
            "descargando": _descarga["hilo"] is not None and _descarga["hilo"].is_alive()}


@app.post("/api/complementos/instalar")
def instalar_complementos():
    from . import complementos
    if not complementos.en_segundo_plano():
        raise HTTPException(409, "Ya se está instalando.")
    return {"ok": True}


@app.post("/api/complementos/cancelar")
def cancelar_complementos():
    from . import complementos
    complementos.cancelar()
    return {"ok": True}


_descarga = {"hilo": None, "parar": threading.Event()}


@app.post("/api/salud/descargar")
def descargar_modelos():
    from .cerebro import ia
    if _descarga["hilo"] is not None and _descarga["hilo"].is_alive():
        raise HTTPException(409, "Ya se están descargando.")
    _descarga["parar"].clear()

    def aviso(msg, p):
        if _descarga["parar"].is_set():
            raise P.Cancelado()
        _estado_ref(mensaje=msg, progreso=round(p), error=None)

    def trabajo():
        try:
            for k, m in ia.MODELOS.items():
                if k == "experto":  # este no se descarga: lo crea la app al estudiar
                    continue
                try:
                    ia.descargar_modelo(m, aviso=aviso)
                except P.Cancelado:
                    raise
                except Exception as e:
                    _estado_ref(error=f"No se pudo descargar {m}: {e}. Pulsa «Descargarlos ahora» para reintentar.")
                    return
            _estado_ref(mensaje="Modelos listos", progreso=100)
        except P.Cancelado:
            _estado_ref(mensaje="Descarga cancelada. Lo ya bajado se conserva; puedes reanudarla cuando quieras.",
                        progreso=0)
    _descarga["hilo"] = threading.Thread(target=trabajo, daemon=True)
    _descarga["hilo"].start()
    return {"ok": True}


@app.post("/api/salud/cancelar")
def cancelar_descarga():
    _descarga["parar"].set()
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
    # también los que quedaron a medias (detenidos o con error), para poder quitarlos
    a_medias = [{"video": d.name, "puede_reanudar": _video_de(d.name) is not None}
                for d in sorted(aprender.FICHAS.glob("*")) if d.is_dir() and not (d / "ficha.json").exists()]
    estado = _estado_ref()
    estado["trabajando"] = _ref["hilo"] is not None and _ref["hilo"].is_alive()
    # se quedó a medias sin estar trabajando: la app se cerró o se pausó
    estado["interrumpido"] = (not estado["trabajando"] and not estado.get("error") and bool(a_medias)
                              and 0 < (estado.get("progreso") or 0) < 100)
    if not aprender.MANUAL.exists() or "videos_base" not in aprender.MANUAL.read_text(encoding="utf-8"):
        aprender.actualizar_manual()  # primera vez: arranca con lo estudiado de fábrica
    manual = json.loads(aprender.MANUAL.read_text(encoding="utf-8"))
    from .cerebro import conocimiento
    base = [{"archivo": f["archivo"], "cortes": f["tomas"]["cortes_por_minuto"],
             "palabras": f["narracion"]["palabras_por_minuto"]} for f in conocimiento.fichas_base()]
    return {"fichas": fichas, "a_medias": a_medias, "base": base, "manual": manual, "estado": estado}


_ref = {"hilo": None, "parar": threading.Event()}
# la tarjeta de 4 GB solo aguanta un trabajo de IA a la vez: estudiar videos, el personaje y el repaso se turnan
_turno = threading.Lock()


def _video_de(video_id: str):
    """El archivo original de un video de referencia (para reanudarlo)."""
    from .cerebro import aprender
    carpeta = aprender.DATOS / "referencias_videos"
    for v in carpeta.glob("*") if carpeta.exists() else []:
        if aprender.ident(v) == video_id:
            return v
    return None


def _empezar_estudio(destino) -> None:
    from .cerebro import aprender
    _ref["parar"].clear()

    def aviso(m, p):
        if _ref["parar"].is_set():
            raise P.Cancelado()
        _estado_ref(mensaje=m, progreso=round(p))

    def trabajo():
        try:
            _estado_ref(video=destino.name, video_id=aprender.ident(destino), error=None,
                        mensaje="Esperando su turno (la IA está ocupada con otra tarea)…", progreso=1, pausado=False)
            with _turno:
                _estado_ref(mensaje="Empezando")
                aprender.aprender(destino, aviso=aviso)
            _estado_ref(mensaje=f"Aprendido: {destino.name}. Ahora repasa lo nuevo.", progreso=100)
            _repasar()
        except P.Cancelado:
            _estado_ref(mensaje=f"En pausa: {destino.name}. Lo ya estudiado está guardado; pulsa «Reanudar» para seguir.",
                        pausado=True)
        except Exception as e:
            import traceback
            _estado_ref(error=str(e), detalle=traceback.format_exc()[-1500:])
    _ref["hilo"] = threading.Thread(target=trabajo, daemon=True)
    _ref["hilo"].start()


@app.post("/api/referencias/reanudar/{video_id}")
def reanudar_referencia(video_id: str):
    if _ref["hilo"] is not None and _ref["hilo"].is_alive():
        raise HTTPException(409, "Ya está estudiando otro video; espera o pausa ese primero.")
    v = _video_de(video_id)
    if v is None:
        raise HTTPException(404, "No encontré el video original; vuelve a soltarlo en la caja.")
    _empezar_estudio(v)
    return {"ok": True}


@app.get("/api/referencias/{video_id}/informe")
def informe_referencia(video_id: str):
    """Todo lo que aprendió de un video, con ejemplos, para mostrarlo en la ventana."""
    from .cerebro import aprender, memoria
    carpeta = (aprender.FICHAS / video_id).resolve()
    if aprender.FICHAS.resolve() not in carpeta.parents or not (carpeta / "ficha.json").exists():
        raise HTTPException(404)

    def leer(nombre, defecto=None):
        r = carpeta / nombre
        return json.loads(r.read_text(encoding="utf-8")) if r.exists() else defecto
    ficha = leer("ficha.json")
    texto = leer("texto.json", {})
    narr = leer("narracion.json", {})
    try:
        ejemplos = memoria.de_video(video_id, 40)
    except Exception:
        ejemplos = []
    return {"ficha": ficha,
            "textos": [e for e in texto.get("elementos", []) if e["tipo"] not in ("marca",)][:80],
            "momentos": [m for v in narr.get("ventanas", []) for m in v.get("momentos", [])][:60],
            "gancho": narr.get("gancho"),
            "tonos": [v.get("tono") for v in narr.get("ventanas", []) if v.get("tono")][:20],
            "memoria": ejemplos}


@app.post("/api/referencias/pausar")
@app.post("/api/referencias/detener")
def detener_referencia():
    if _ref["hilo"] is not None and _ref["hilo"].is_alive():
        _ref["parar"].set()
        _estado_ref(mensaje="Pausando… (termina el paso que está haciendo y se guarda)")
    return {"ok": True}


@app.delete("/api/referencias/{video_id}")
def quitar_referencia(video_id: str):
    """Olvida un video de referencia: su ficha, su copia y lo que dejó en la memoria."""
    from .cerebro import aprender, memoria
    if _ref["hilo"] is not None and _ref["hilo"].is_alive() and _estado_ref().get("video_id") == video_id:
        raise HTTPException(409, "Ese video se está estudiando ahora; deténlo primero.")
    carpeta = (aprender.FICHAS / video_id).resolve()
    if aprender.FICHAS.resolve() not in carpeta.parents:
        raise HTTPException(400)
    shutil.rmtree(carpeta, ignore_errors=True)
    for v in (aprender.DATOS / "referencias_videos").glob("*"):
        if aprender.ident(v) == video_id:
            v.unlink(missing_ok=True)
    try:
        memoria.borrar_video(video_id)
    except Exception:
        pass
    aprender.actualizar_manual()
    _estado_ref(mensaje=f"Se quitó {video_id}", error=None, progreso=0)
    return {"ok": True}


@app.post("/api/referencias")
async def nueva_referencia(video: UploadFile = File(...)):
    from .cerebro import aprender
    if _ref["hilo"] is not None and _ref["hilo"].is_alive():
        raise HTTPException(409, "Ya está estudiando otro video; espera o deténlo.")
    destino = aprender.DATOS / "referencias_videos" / video.filename
    destino.parent.mkdir(parents=True, exist_ok=True)
    with destino.open("wb") as f:
        shutil.copyfileobj(video.file, f)

    _empezar_estudio(destino)
    return {"ok": True}


# ---------- estudio: la IA estudia todo lo que sabe, se examina y crea su modelo propio ----------
_est = {"hilo": None, "parar": threading.Event()}


def _repasar(forzar: bool = False) -> None:
    from .cerebro import estudio
    if _est["hilo"] is not None and _est["hilo"].is_alive():
        return

    _est["parar"].clear()

    def aviso(m, p):
        if _est["parar"].is_set():
            raise P.Cancelado()

    def trabajo():
        try:
            with _turno:
                estudio.estudiar(aviso=aviso, forzar=forzar)
        except P.Cancelado:
            estudio._estado(trabajando=False, mensaje="Estudio en pausa. Lo leído está guardado; «Reanudar» sigue.",
                            pausado=True)
        except Exception:
            pass  # el error queda en el estado del estudio
    _est["hilo"] = threading.Thread(target=trabajo, daemon=True)
    _est["hilo"].start()


@app.get("/api/estudio")
def ver_estudio():
    from .cerebro import estudio
    e = estudio.estado()
    e["trabajando"] = _est["hilo"] is not None and _est["hilo"].is_alive()
    if e.get("trabajando") and _turno.locked() and e.get("progreso", 0) <= 1:
        e["mensaje"] = "Esperando su turno…"
    return e


@app.post("/api/estudio")
def hacer_estudio():
    from .cerebro import ia
    if not ia.disponible():
        raise HTTPException(409, "Ollama no está abierto.")
    _repasar(forzar=True)
    return {"ok": True}


@app.post("/api/estudio/pausar")
def pausar_estudio():
    _est["parar"].set()
    return {"ok": True}


@app.post("/api/estudio/reanudar")
def reanudar_estudio():
    from .cerebro import estudio
    estudio._estado(pausado=False)
    _repasar(forzar=True)
    return {"ok": True}


@app.post("/api/preguntar")
def preguntar(pregunta: str = Form(...)):
    """Preguntarle al editor experto (responde con lo que estudió y lo que tiene en la memoria)."""
    from .cerebro import estudio, ia
    if not ia.disponible():
        raise HTTPException(409, "Ollama no está abierto.")
    if not _turno.acquire(timeout=5):
        raise HTTPException(409, "La IA está ocupada estudiando; pregúntale cuando termine o pausa el estudio.")
    try:
        return {"respuesta": estudio.sugerir(pregunta[:800])}
    finally:
        _turno.release()


# ---------- el personaje: estudia los clips de cómo debe hablar el mapache ----------
_pj = {"hilo": None, "estado": {}}


@app.get("/api/personaje")
def ver_personaje():
    from .cerebro import personaje
    clips = []
    for c in sorted(personaje.CARPETA.glob("*/lineas.json")):
        d = json.loads(c.read_text(encoding="utf-8"))
        clips.append({"video": d["video"], "archivo": d["archivo"], "rol": d["rol"], "frases": len(d["lineas"]),
                      "lineas": [{k: x.get(k) for k in ("inicio", "hablante", "texto", "registro", "recursos",
                                                         "insultos", "por_que_da_risa", "tono_hz", "sobresale_db",
                                                         "palabras_s", "entonacion")} for x in d["lineas"]]})
    return {"perfil": personaje.perfil(), "clips": clips,
            "estado": dict(_pj["estado"], trabajando=_pj["hilo"] is not None and _pj["hilo"].is_alive())}


@app.post("/api/personaje")
async def nuevo_clip_personaje(video: UploadFile = File(...), rol: str = Form("todo")):
    from .cerebro import aprender, personaje
    if _pj["hilo"] is not None and _pj["hilo"].is_alive():
        raise HTTPException(409, "Ya está estudiando un clip del personaje; espera a que termine.")
    if rol not in ("calma", "rabia", "todo"):
        rol = "todo"
    destino = aprender.DATOS / "personaje_videos" / Path(video.filename).name
    destino.parent.mkdir(parents=True, exist_ok=True)
    with destino.open("wb") as f:
        shutil.copyfileobj(video.file, f)

    def aviso(m, p):
        _pj["estado"] = {"mensaje": m, "progreso": round(p), "archivo": destino.name}

    def trabajo():
        try:
            aviso("Esperando su turno (la IA está ocupada con otra tarea)…", 1)
            with _turno:
                personaje.estudiar_clip(destino, rol, aviso)
                personaje.armar_perfil(aviso)
            aviso(f"Personaje actualizado con {destino.name}. Ahora repasa lo nuevo.", 100)
            _repasar()
        except Exception as e:
            _pj["estado"] = {"error": str(e), "archivo": destino.name}
    _pj["hilo"] = threading.Thread(target=trabajo, daemon=True)
    _pj["hilo"].start()
    return {"ok": True}


@app.delete("/api/personaje/{video_id}")
def quitar_clip_personaje(video_id: str):
    from .cerebro import personaje
    if _pj["hilo"] is not None and _pj["hilo"].is_alive():
        raise HTTPException(409, "Está estudiando un clip; espera a que termine.")
    personaje.quitar(video_id)
    if any(personaje.CARPETA.glob("*/lineas.json")):
        with _turno:
            personaje.armar_perfil()
    else:
        personaje.PERFIL.unlink(missing_ok=True)
    return {"ok": True}


def _al_arrancar() -> None:
    """Al abrir la app: si el conocimiento cambió (actualización nueva, videos o personaje), lo vuelve a estudiar."""
    import time
    from .cerebro import estudio, ia
    for _ in range(60):  # espera a que Ollama esté abierto (hasta 5 minutos)
        if ia.disponible():
            break
        time.sleep(5)
    else:
        return
    try:
        hay = set(ia.instalados())
        if any(m not in hay and m + ":latest" not in hay for k, m in ia.MODELOS.items() if k != "experto"):
            return  # faltan modelos: primero se descargan desde la ventana
        if not estudio.estado().get("al_dia"):
            _repasar()
    except Exception:
        pass


# ---------- actualizaciones ----------
@app.get("/api/actualizacion")
def ver_actualizacion():
    from . import actualizar
    return actualizar.buscar() | {"estado": actualizar.estado}


@app.post("/api/actualizacion")
def hacer_actualizacion():
    from . import actualizar
    info = actualizar.buscar()
    if not info.get("hay") or not info.get("rapida") or not info.get("app_zip"):
        raise HTTPException(409, "Esta versión necesita el instalador completo.")
    ocupado = [h for h in (_ref["hilo"], _est["hilo"], _pj["hilo"]) if h is not None and h.is_alive()]
    if any(p.trabajando for p in _abiertos.values()) or ocupado:
        raise HTTPException(409, "Espera a que termine (o detén) lo que está trabajando antes de actualizar.")
    actualizar.aplicar(info["app_zip"])
    return {"ok": True}


@app.get("/api/actualizacion/estado")
def estado_actualizacion():
    from . import actualizar
    return actualizar.estado


@app.get("/api/version")
def version():
    from . import actualizar
    return {"version": actualizar.version_local()}


def abrir(puerto: int = 8765, ventana: bool = True) -> None:
    import uvicorn
    from . import complementos
    complementos.en_segundo_plano()  # herramientas nuevas de esta versión
    threading.Thread(target=_al_arrancar, daemon=True).start()
    if ventana:
        threading.Timer(1.5, lambda: webbrowser.open(f"http://127.0.0.1:{puerto}")).start()
    uvicorn.run(app, host="127.0.0.1", port=puerto, log_level="warning")


if __name__ == "__main__":
    abrir()
