"""Capa 1 · Tomas y transiciones.

Detecta cada toma con TransNetV2 (red neuronal entrenada para cortes y transiciones graduales)
y clasifica cómo se pasa de una toma a la siguiente:

  corte      cambio seco de un fotograma al otro
  fundido    el cambio dura varios fotogramas (disolvencia, barrido)
  a_negro    la imagen se apaga antes de cambiar
  destello   un fotograma muy claro en el cambio (flash blanco)

Si TransNetV2 no está instalado, se usa PySceneDetect y todas las transiciones quedan como cortes.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import numpy as np

UMBRAL = 0.5


def _fps(video: Path) -> float:
    s = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                        "stream=avg_frame_rate", "-of", "csv=p=0", str(video)],
                       capture_output=True, text=True).stdout.strip()
    n, d = (s.split("/") + ["1"])[:2]
    return float(n) / float(d or 1)


def _luz(fotos: np.ndarray) -> np.ndarray:
    f = fotos.astype(np.float32)
    return 0.299 * f[..., 0].mean((1, 2)) + 0.587 * f[..., 1].mean((1, 2)) + 0.114 * f[..., 2].mean((1, 2))


def _clasificar(ini_hueco: int, fin_hueco: int, luz: np.ndarray) -> str:
    a = max(0, ini_hueco - 3)
    b = min(len(luz) - 1, fin_hueco + 3)
    tramo = luz[a:b + 1]
    vecinos = np.r_[luz[max(0, a - 6):a], luz[b + 1:b + 7]]
    base = float(np.median(vecinos)) if len(vecinos) else float(np.median(tramo))
    if tramo.max() > max(200, base + 70):
        return "destello"
    if tramo.min() < 18 and base > 40:
        return "a_negro"
    if fin_hueco - ini_hueco >= 2:
        return "fundido"
    return "corte"


def con_transnet(video: Path) -> list[dict]:
    import torch
    from transnetv2_pytorch import TransNetV2
    modelo = TransNetV2(device="auto")
    modelo.eval()
    with torch.no_grad():
        fotos, una, todas = modelo.predict_video(str(video), quiet=True)
    fotos = fotos.cpu().numpy()
    una = una.cpu().numpy().reshape(-1)
    escenas = modelo.predictions_to_scenes(una, UMBRAL)
    luz = _luz(fotos)
    fps = _fps(video)
    tomas = []
    for i, (ini, fin) in enumerate(escenas):
        trans = "inicio"
        if i > 0:
            fin_prev = int(escenas[i - 1][1])
            trans = _clasificar(fin_prev, int(ini), luz)
        tomas.append({"n": i + 1, "inicio": round(ini / fps, 3), "fin": round((fin + 1) / fps, 3),
                      "entrada": trans, "confianza": round(float(una[max(0, ini - 1):ini + 1].max()), 3)})
    return tomas


def con_pyscenedetect(video: Path) -> list[dict]:
    from scenedetect import AdaptiveDetector, detect
    escenas = detect(str(video), AdaptiveDetector(), show_progress=False)
    return [{"n": i + 1, "inicio": round(a.get_seconds(), 3), "fin": round(b.get_seconds(), 3),
             "entrada": "inicio" if i == 0 else "corte", "confianza": None}
            for i, (a, b) in enumerate(escenas)]


def resumen(tomas: list[dict], dur: float) -> dict:
    d = np.array([t["fin"] - t["inicio"] for t in tomas]) if tomas else np.array([dur])
    tipos: dict[str, int] = {}
    for t in tomas[1:]:
        tipos[t["entrada"]] = tipos.get(t["entrada"], 0) + 1
    # ritmo por minuto: cuántos cortes caen en cada minuto
    por_min = np.bincount([int(t["inicio"] // 60) for t in tomas[1:]], minlength=int(dur // 60) + 1)
    return {"tomas": len(tomas), "cortes_por_minuto": round(60 * (len(tomas) - 1) / max(dur, 1), 1),
            "duracion_toma": {"mediana": round(float(np.median(d)), 2), "p10": round(float(np.percentile(d, 10)), 2),
                              "p90": round(float(np.percentile(d, 90)), 2), "max": round(float(d.max()), 2)},
            "transiciones": tipos, "cortes_por_minuto_serie": por_min.tolist()}


def analizar(video: Path, carpeta: Path, dur: float) -> dict:
    destino = carpeta / "tomas.json"
    if destino.exists():
        return json.loads(destino.read_text(encoding="utf-8"))
    try:
        tomas, metodo = con_transnet(video), "transnetv2"
    except ImportError:
        tomas, metodo = con_pyscenedetect(video), "pyscenedetect"
    datos = {"metodo": metodo, "tomas": tomas, "resumen": resumen(tomas, dur)}
    destino.write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")
    return datos
