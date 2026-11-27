"""Banco: compara modelos de visión sobre las mismas tomas de una película libre.

Guarda en salida/vision/: tomas.json, una carpeta por modelo con imagen.json y tiempos.json,
y los fotogramas en miniatura para revisarlos.
Uso: python -m pruebas.banco.vision VIDEO MODELO [MODELO...]
"""
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

from resumen_editor.cerebro import ia, imagen, tomas

N_TOMAS = 30


def main(video: str, *modelos: str) -> None:
    salida = Path("salida/vision")
    salida.mkdir(parents=True, exist_ok=True)
    clip = salida / "clip.mp4"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-ss", "900", "-t", "120", "-i", video,
                    "-vf", "scale=-2:480", "-c:v", "libx264", "-preset", "veryfast", "-an", str(clip)], check=True)
    trabajo = salida / "comun"
    trabajo.mkdir(exist_ok=True)
    t = time.time()
    datos = tomas.analizar(clip, trabajo, 120)
    print("tomas", datos["resumen"], round(time.time() - t, 1), "s")
    elegidas = datos["tomas"][:N_TOMAS]
    for m in modelos:
        ia.MODELOS["vision"] = m
        ia.descargar_modelo(m)
        carpeta = salida / m.replace(":", "_")
        carpeta.mkdir(exist_ok=True)
        (carpeta / "fotogramas").mkdir(exist_ok=True)
        for f in (trabajo / "fotogramas").glob("*.jpg") if (trabajo / "fotogramas").exists() else []:
            shutil.copy(f, carpeta / "fotogramas" / f.name)
        t = time.time()
        try:
            vistas = imagen.analizar(clip, carpeta, elegidas)
            error = None
        except Exception as e:
            vistas, error = [], repr(e)
        seg = round(time.time() - t, 1)
        (carpeta / "tiempos.json").write_text(json.dumps({"modelo": m, "segundos": seg, "tomas": len(vistas),
                                                          "error": error}, ensure_ascii=False))
        print(m, seg, "s", len(vistas), "tomas", error or "")
    clip.unlink()


if __name__ == "__main__":
    main(*sys.argv[1:])
