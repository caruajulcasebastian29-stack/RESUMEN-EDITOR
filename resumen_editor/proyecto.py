"""Un proyecto = un resumen de la App 1 que la App 2 rehace. Orquesta los pasos y guarda el estado en disco.

Carpeta del proyecto (en Documentos/Resumen Editor/proyectos/<nombre>/):
  origen.mp4          copia del video de la App 1
  entender/           análisis completo: tomas, audio separado, palabras, imagen, mapa de la historia, diagnóstico
  limpieza.json       logo detectado y tramos excluidos (Jhon puede desmarcar)
  fondo.wav           sonido de la película sin la narración robótica (sale de la separación)
  guion.json          narración nueva del mapache
  voz/NNN.wav         una voz por frase
  trabajo/            piezas del montaje
  revision.json       autorrevisión con medidas
  lotes.json          lotes con su estado: pendiente / ok / rehacer + comentario
  resumen.mp4         resultado
  estado.json         paso actual y mensajes para la ventana
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import threading
import traceback
from pathlib import Path

from . import guion as guion_mod
from . import limpieza, lotes, montaje
from .config import estilo

DATOS = Path(os.environ.get("RESUMEN_EDITOR_DATOS", Path.home() / "Documents" / "Resumen Editor"))
PROYECTOS = DATOS / "proyectos"
AJUSTES = DATOS / "ajustes.json"
os.environ.setdefault("RESUMEN_EDITOR_DATOS", str(DATOS))
os.environ.setdefault("RESUMEN_EDITOR_MODELOS", str(DATOS / "modelos"))

class Cancelado(Exception):
    """Jhon pulsó «Detener»: el trabajo se corta en el siguiente punto seguro."""


PASOS = ["entender", "limpieza", "guion", "voz", "montaje", "revision", "lotes"]


def ajustes() -> dict:
    base = {"motor_voz": "generica", "acento": "peru", "clave_gemini": "", "voz_base": "Algenib",
            "tamano": [1920, 1080], "mostrar_mapache": False}
    if AJUSTES.exists():
        base.update(json.loads(AJUSTES.read_text(encoding="utf-8")))
    return base


def guardar_ajustes(nuevos: dict) -> None:
    DATOS.mkdir(parents=True, exist_ok=True)
    a = ajustes()
    a.update(nuevos)
    AJUSTES.write_text(json.dumps(a, ensure_ascii=False, indent=1), encoding="utf-8")


def manual() -> dict:
    from .cerebro import aprender
    return json.loads(aprender.MANUAL.read_text(encoding="utf-8")) if aprender.MANUAL.exists() else {}


class Proyecto:
    def __init__(self, carpeta: Path):
        self.dir = Path(carpeta)
        self._hilo: threading.Thread | None = None
        self._parar = threading.Event()

    @property
    def trabajando(self) -> bool:
        return self._hilo is not None and self._hilo.is_alive()

    def revisar_parada(self) -> None:
        if self._parar.is_set():
            raise Cancelado()

    def detener(self) -> None:
        if self.trabajando:
            self._parar.set()
            self.guardar_estado(mensaje="Pausando… (termina el paso que está haciendo y se guarda)")

    def eliminar(self) -> None:
        """Borra el proyecto entero. Si está trabajando, primero lo detiene."""
        if self.trabajando:
            self._parar.set()
            self._hilo.join(timeout=120)
            if self.trabajando:
                raise RuntimeError("El proyecto sigue ocupado en un paso largo; prueba otra vez en un minuto.")
        shutil.rmtree(self.dir, ignore_errors=True)

    # ---------- creación y estado ----------
    @classmethod
    def crear(cls, video: Path, nombre: str | None = None) -> "Proyecto":
        nombre = nombre or Path(video).stem
        carpeta = PROYECTOS / nombre
        carpeta.mkdir(parents=True, exist_ok=True)
        destino = carpeta / "origen.mp4"
        if not destino.exists():
            shutil.copy2(video, destino)
        p = cls(carpeta)
        p.guardar_estado(paso="creado", progreso=0, mensaje="Proyecto creado")
        return p

    @property
    def origen(self) -> Path:
        return self.dir / "origen.mp4"

    @property
    def analisis(self) -> Path:
        return self.dir / "entender"

    def leer(self, nombre: str, defecto=None):
        ruta = self.dir / nombre
        return json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else defecto

    def escribir(self, nombre: str, datos) -> None:
        (self.dir / nombre).write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")

    def estado(self) -> dict:
        return self.leer("estado.json", {"paso": "creado", "progreso": 0, "mensaje": ""})

    def guardar_estado(self, **campos) -> None:
        e = self.estado() if (self.dir / "estado.json").exists() else {}
        e.update(campos)
        self.escribir("estado.json", e)

    def _aviso(self, paso: str):
        def aviso(mensaje, progreso):
            self.revisar_parada()
            self.guardar_estado(paso=paso, mensaje=mensaje, progreso=round(progreso))
        return aviso

    # ---------- pasos ----------
    def entender(self) -> dict:
        from .cerebro import entender
        datos = entender.entender(self.origen, self.analisis, manual(), aviso=self._aviso("entender"))
        musica = self.analisis / "musica.wav"
        if musica.exists() and not (self.dir / "fondo.wav").exists():
            shutil.copy2(musica, self.dir / "fondo.wav")
        return datos

    def limpiar(self) -> None:
        self.guardar_estado(paso="limpieza", mensaje="Buscando logos y publicidad…", progreso=0)
        pal = self.leer("entender/palabras.json", {"tramos": []})
        excluidos = limpieza.tramos_autopromocion([t for t in pal["tramos"]])
        self.escribir("limpieza.json", {"logo": limpieza.detectar_logo(self.origen), "excluidos": excluidos})

    def escribir_guion(self) -> None:
        from .cerebro import escribir
        mapa = self.leer("entender/mapa.json")
        escribir.escribir(self.dir, mapa, manual(), aviso=self._aviso("guion"))
        _, frases = guion_mod.cargar(self.dir / "guion.json")
        self.guardar_estado(avisos_guion=guion_mod.revisar(frases, mapa["hechos"][-1]["fin"] if mapa["hechos"] else 60))

    def _motor_voz(self):
        from . import voz
        a = ajustes()
        if a["motor_voz"] == "gemini" and a["clave_gemini"]:
            return voz.VozGemini(a["clave_gemini"], a["voz_base"])
        if a["motor_voz"] == "prueba":
            return voz.VozPrueba(Path(os.environ["RESUMEN_EDITOR_MODELOS"]) / "vits-coqui-es-css10")
        return voz.VozGenerica(a["acento"])

    def generar_voz(self, solo: set[int] | None = None) -> None:
        self.guardar_estado(paso="voz", mensaje="Grabando la voz…", progreso=0)
        motor = self._motor_voz()
        _, frases = guion_mod.cargar(self.dir / "guion.json")
        for i, f in enumerate(frases):
            destino = self.dir / "voz" / f"{f.id:03d}.wav"
            if (solo is None and destino.exists()) or (solo is not None and f.id not in solo):
                continue
            self.revisar_parada()
            motor.generar(f, destino)
            self.guardar_estado(progreso=round(100 * (i + 1) / len(frases)))

    def _elector(self):
        from .cerebro.cortes import Elector
        return Elector(self.leer("entender/tomas.json")["tomas"], self.leer("entender/imagen.json", []),
                       self.leer("entender/diagnostico.json", {}), manual())

    def montar(self, solo: set[int] | None = None) -> None:
        self.guardar_estado(paso="montaje", mensaje="Armando el video…", progreso=0)
        limp = self.leer("limpieza.json")
        excluidos = [x for x in limp["excluidos"] if not x.get("desmarcado")]
        fondo = self.dir / "fondo.wav"
        _, frases = guion_mod.cargar(self.dir / "guion.json")
        tam = tuple(ajustes()["tamano"])
        elector = self._elector()
        partes = []
        for i, f in enumerate(frases):
            self.revisar_parada()
            pieza = self.dir / "trabajo" / f"frase_{f.id:03d}.mp4"
            hecha = self.dir / "trabajo" / f"frase_{f.id:03d}.json"
            if pieza.exists() and hecha.exists() and not (solo and f.id in solo):
                for s, e in json.loads(hecha.read_text())["trozos"]:  # lo ya montado cuenta como usado
                    elector.usadas.update(t["n"] for t in elector.tomas if t["inicio"] < e and t["fin"] > s)
            else:
                montaje.montar_frase(f, self.dir / "voz" / f"{f.id:03d}.wav", self.origen, [], excluidos,
                                     limp["logo"], tam, self.dir / "trabajo", fondo if fondo.exists() else None,
                                     elector=elector, mapache=ajustes()["mostrar_mapache"])
            partes.append(pieza)
            self.guardar_estado(progreso=round(100 * (i + 1) / len(frases)))
        montaje.unir(partes, self.dir / "resumen.mp4")
        self.revisar()
        self.preparar_lotes(partes, frases)

    def revisar(self) -> dict:
        """Autorrevisión: mide el resultado contra lo aprendido de las referencias."""
        from .cerebro import tomas as T
        self.guardar_estado(paso="revision", mensaje="Revisando el resultado…", progreso=0)
        carpeta = self.dir / "revision"
        carpeta.mkdir(exist_ok=True)
        (carpeta / "tomas.json").unlink(missing_ok=True)
        dur = montaje.duracion_audio(self.dir / "resumen.mp4")
        r = T.analizar(self.dir / "resumen.mp4", carpeta, dur)["resumen"]
        m = manual()
        ref = (m.get("cortes_por_minuto") or {}).get("mediana")
        datos = {"cortes_por_minuto": r["cortes_por_minuto"], "referencia_cortes_por_minuto": ref,
                 "toma_mas_larga_s": r["duracion_toma"]["max"], "duracion_s": round(dur, 1),
                 "ritmo_ok": (abs(r["cortes_por_minuto"] - ref) <= ref * 0.25) if ref else None}
        self.escribir("revision.json", datos)
        return datos

    def preparar_lotes(self, partes: list[Path], frases) -> None:
        durs = [montaje.duracion_audio(p) for p in partes]
        anteriores = {tuple(l["frases"]): l for l in self.leer("lotes.json", [])}
        grupos = lotes.partir(durs)
        datos, t = [], 0.0
        for n, g in enumerate(grupos, 1):
            ids = [frases[i].id for i in g]
            dur = sum(durs[i] for i in g)
            archivo = f"lote_{n:02d}.mp4"
            montaje.unir([partes[i] for i in g], self.dir / "trabajo" / archivo)
            previo = anteriores.get(tuple(ids), {})
            datos.append({"n": n, "frases": ids, "inicio": round(t, 2), "dur": round(dur, 2), "archivo": archivo,
                          "estado": previo.get("estado", "pendiente"), "comentario": previo.get("comentario", "")})
            t += dur
        self.escribir("lotes.json", datos)
        self.guardar_estado(paso="lotes", progreso=100, mensaje="Listo para revisar por lotes")

    def marcar_lote(self, n: int, ok: bool, comentario: str = "") -> None:
        datos = self.leer("lotes.json")
        guion = self.leer("guion.json")
        por_id = {f["id"]: f for f in guion["frases"]}
        for l in datos:
            if l["n"] == n:
                l["estado"], l["comentario"] = ("ok" if ok else "rehacer"), comentario
                lotes.aprender([por_id[i]["texto"] for i in l["frases"]], ok, comentario)
        self.escribir("lotes.json", datos)

    def rehacer_marcados(self) -> None:
        from .cerebro import escribir
        datos = self.leer("lotes.json")
        guion = self.leer("guion.json")
        mapa = self.leer("entender/mapa.json")
        frases = list(guion["frases"])
        siguiente_id = max(f["id"] for f in frases) + 1
        rehechos: set[int] = set()
        for l in [x for x in datos if x["estado"] == "rehacer"]:
            self.guardar_estado(paso="rehacer", mensaje=f"Rehaciendo el lote {l['n']}…")
            idx = [i for i, f in enumerate(frases) if f["id"] in l["frases"]]
            anterior = frases[idx[0] - 1]["texto"] if idx[0] > 0 else ""
            siguiente = frases[idx[-1] + 1]["texto"] if idx[-1] + 1 < len(frases) else ""
            nuevas = escribir.rehacer([frases[i] for i in idx], mapa, manual(), l["comentario"], anterior, siguiente)
            for f in nuevas:
                f["id"] = siguiente_id
                rehechos.add(siguiente_id)
                siguiente_id += 1
            frases[idx[0]:idx[-1] + 1] = nuevas
        guion["frases"] = frases
        self.escribir("guion.json", guion)
        self.generar_voz(solo=rehechos)
        self.montar(solo=rehechos)

    def exportar(self, formato: str = "youtube", partes: int = 1) -> list[Path]:
        cfg = estilo("montaje")["exportar"]
        W, H = cfg[formato]
        origen = self.dir / "resumen.mp4"
        dur = montaje.duracion_audio(origen)
        salidas = []
        for i in range(partes):
            destino = self.dir / f"{self.dir.name}_{formato}{'_parte' + str(i + 1) if partes > 1 else ''}.mp4"
            if formato == "tiktok":  # vertical: imagen al centro con fondo desenfocado
                vf = (f"split[a][b];[a]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},boxblur=20[f];"
                      f"[b]scale={W}:-2[c];[f][c]overlay=(W-w)/2:(H-h)/2")
            else:
                vf = f"scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2"
            subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-ss", f"{dur * i / partes:.2f}",
                            "-t", f"{dur / partes:.2f}", "-i", str(origen), "-vf", vf, "-c:v", "libx264",
                            "-preset", "medium", "-crf", "19", "-c:a", "aac", "-b:a", "192k", str(destino)], check=True)
            salidas.append(destino)
        return salidas

    # ---------- en segundo plano ----------
    def correr_todo(self) -> None:
        if self.trabajando:
            return
        self._parar.clear()

        def trabajo():
            try:
                if not (self.analisis / "diagnostico.json").exists():
                    self.entender()
                if not (self.dir / "limpieza.json").exists():
                    self.limpiar()
                if not (self.dir / "guion.json").exists():
                    self.escribir_guion()
                self.generar_voz()
                self.montar()
            except Cancelado:
                if self.dir.exists():
                    self.guardar_estado(mensaje="En pausa. Lo hecho hasta aquí está guardado; «Reanudar» sigue desde ahí.",
                                        detenido=True)
            except Exception as e:  # el error se muestra en la ventana, no en una consola
                if self.dir.exists():
                    self.guardar_estado(error=f"{e}", detalle=traceback.format_exc()[-1500:])
        self._hilo = threading.Thread(target=trabajo, daemon=True)
        self._hilo.start()


def listar() -> list[dict]:
    if not PROYECTOS.exists():
        return []
    return [{"nombre": d.name, **Proyecto(d).estado()} for d in sorted(PROYECTOS.iterdir()) if d.is_dir()]
