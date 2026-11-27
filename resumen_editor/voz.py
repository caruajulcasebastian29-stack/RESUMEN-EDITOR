"""Voz del mapache: genera un audio por frase con la emoción que pide el guion.

Motores:
- "gemini": Gemini TTS (gratis con clave de Google AI Studio). El tono se dirige con una instrucción escrita.
- "prueba": voz local provisional (Piper/VITS) solo para probar el montaje. No es la voz final.
La voz definitiva del mapache sigue pendiente de elegir (ver docs/10-diseno-app.md, sección 8).
"""
from __future__ import annotations

import base64
import json
import subprocess
import urllib.request
import wave
from pathlib import Path

from .config import estilo
from .guion import Frase

INSTRUCCION = {
    "tranquilo": "relajado y en confianza, como contándole un chisme a un amigo en la esquina, con sarcasmo suave",
    "burla": "burlón, con una risita contenida",
    "aburrido": "aburrido, arrastrando las palabras",
    "pensando": "pensativo, despacio",
    "risa": "riéndose mientras habla",
    "asco": "con asco, como diciendo «no puede ser»",
    "furioso": "indignado, reclamando a gritos, cada vez más rápido y más fuerte, exagerando como víctima",
    "groseria": "furioso, gritando el insulto final",
}


def descripcion_voz() -> str:
    p = estilo("narrador")["personaje"]
    return f"Un mapache narrador de barrio, voz {p['voz']}, acento {p['acento']}."


class VozGemini:
    MODELO = "gemini-2.5-flash-preview-tts"

    def __init__(self, clave: str, voz_base: str = "Algenib"):
        self.clave, self.voz_base = clave, voz_base

    def generar(self, f: Frase, destino: Path) -> Path:
        tono = INSTRUCCION.get(f.emocion, INSTRUCCION["tranquilo"])
        texto = f"{descripcion_voz()} Dilo {tono}: {f.hablado}"
        cuerpo = {
            "contents": [{"parts": [{"text": texto}]}],
            "generationConfig": {"responseModalities": ["AUDIO"],
                                 "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": self.voz_base}}}},
        }
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.MODELO}:generateContent?key={self.clave}"
        req = urllib.request.Request(url, json.dumps(cuerpo).encode(), {"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=120) as r:
            datos = json.load(r)
        pcm = base64.b64decode(datos["candidates"][0]["content"]["parts"][0]["inlineData"]["data"])
        destino.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(destino), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(24000)
            w.writeframes(pcm)
        return destino


class VozGenerica:
    """Voz provisional mientras se define la del mapache: voces neuronales de Microsoft Edge
    (gratis, necesitan internet). Hay voces con acento peruano y panameño.

    Para que no suene plana, cada frase se parte en sus oraciones (puntos, signos) y cada
    trozo lleva su propia velocidad, tono y volumen:
      - el tono y la velocidad que pidió el guionista para la frase;
      - las preguntas suben de tono y las exclamaciones suben de volumen;
      - el último trozo de un remate va un poco más lento, con una pausa antes;
      - la frustración y la furia aceleran trozo a trozo (se va calentando).
    Las velocidades parten de lo medido en las voces de referencia (palabras por segundo)."""

    VOCES = {"peru": "es-PE-AlexNeural", "panama": "es-PA-RobertoNeural", "mexico": "es-MX-JorgeNeural"}
    AJUSTE = {  # (velocidad %, tono Hz, volumen %)
        "tranquilo": (-6, -6, 0), "burla": (0, -2, 0), "aburrido": (-14, -8, -5), "pensando": (-12, -4, -5),
        "risa": (6, 4, 5), "asco": (-4, -2, 0), "frustrado": (4, 2, 5), "sorpresa": (6, 10, 8),
        "triste": (-14, -10, -8), "misterio": (-12, -8, -6), "furioso": (14, 10, 15), "groseria": (18, 14, 20),
    }
    VELOCIDAD = {"lenta": -12, "normal": 0, "rapida": 12}
    PAUSAS = {",": 0.12, ";": 0.18, ":": 0.2, ".": 0.32, "…": 0.45, "?": 0.3, "!": 0.3}

    def __init__(self, acento: str = "peru"):
        self.voz = self.VOCES.get(acento, acento)

    @staticmethod
    def clausulas(texto: str) -> list[tuple[str, str]]:
        """Trozos de la frase con el signo que los cierra."""
        import re
        # solo se parte en finales de oración: las comas las respira bien la propia voz,
        # y partir más fino suena entrecortado
        trozos = re.findall(r"[^.…?!]+[.…?!]*", texto)
        salida = []
        for t in trozos:
            t = t.strip()
            if not t:
                continue
            signo = re.search(r"[.…?!]+$", t)
            salida.append((t, signo.group(0)[-1] if signo else ""))
        return salida or [(texto, "")]

    def _trozo(self, texto: str, v: int, t: int, vol: int, destino: Path) -> Path:
        import asyncio
        import edge_tts
        com = edge_tts.Communicate(texto, self.voz, rate=f"{v:+d}%", pitch=f"{t:+d}Hz", volume=f"{vol:+d}%")
        asyncio.run(com.save(str(destino)))
        return destino

    def generar(self, f: Frase, destino: Path) -> Path:
        emocion = "furioso" if f.rata and f.emocion == "tranquilo" else f.emocion
        v0, t0, vol0 = self.AJUSTE.get(emocion, self.AJUSTE["tranquilo"])
        v0 += self.VELOCIDAD.get(getattr(f, "velocidad", "normal"), 0)
        destino.parent.mkdir(parents=True, exist_ok=True)
        trozos = self.clausulas(f.hablado)
        partes, lista = [], destino.with_suffix(".lista.txt")
        for k, (texto, signo) in enumerate(trozos):
            v, t, vol = v0, t0, vol0
            if emocion in ("frustrado", "furioso", "groseria"):
                v += 4 * k  # se va calentando
                t += 2 * k
            if signo == "?":
                t += 8
            if signo == "!":
                vol += 8
                v += 4
            ultimo = k == len(trozos) - 1
            if ultimo and len(trozos) > 1 and emocion in ("burla", "tranquilo"):
                v -= 6  # el remate, un poco más despacio
            mp3 = destino.with_name(f"{destino.stem}_{k:02d}.mp3")
            self._trozo(texto, max(-40, min(40, v)), max(-30, min(30, t)), max(-30, min(40, vol)), mp3)
            partes.append(mp3)
            pausa = self.PAUSAS.get(signo, 0.08)
            if not ultimo and k == len(trozos) - 2 and emocion in ("burla", "tranquilo", "frustrado"):
                pausa += 0.2  # respiro antes del remate
            silencio = destino.with_name(f"{destino.stem}_{k:02d}_s.wav")
            subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                            f"anullsrc=r=24000:cl=mono", "-t", f"{pausa if not ultimo else 0.05:.2f}", str(silencio)],
                           check=True)
            partes.append(silencio)
        entradas = []
        for p in partes:
            entradas += ["-i", str(p)]
        filtro = "".join(f"[{i}:a]aresample=24000,aformat=channel_layouts=mono[a{i}];" for i in range(len(partes)))
        filtro += "".join(f"[a{i}]" for i in range(len(partes))) + f"concat=n={len(partes)}:v=0:a=1[s]"
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", *entradas, "-filter_complex", filtro, "-map", "[s]",
                        "-ac", "1", "-ar", "24000", str(destino)], check=True)
        for p in partes:
            p.unlink(missing_ok=True)
        lista.unlink(missing_ok=True)
        return destino


class VozPrueba:
    """Voz local provisional para probar el montaje sin internet."""

    def __init__(self, carpeta_modelo: Path):
        import sherpa_onnx
        carpeta_modelo = Path(carpeta_modelo)
        onnx = next(carpeta_modelo.glob("*.onnx"))
        extra = {"data_dir": str(carpeta_modelo / "espeak-ng-data")} if (carpeta_modelo / "espeak-ng-data").is_dir() else {}
        cfg = sherpa_onnx.OfflineTtsConfig(model=sherpa_onnx.OfflineTtsModelConfig(
            vits=sherpa_onnx.OfflineTtsVitsModelConfig(
                model=str(onnx), tokens=str(carpeta_modelo / "tokens.txt"), **extra), num_threads=4))
        self.tts = sherpa_onnx.OfflineTts(cfg)

    def generar(self, f: Frase, destino: Path) -> Path:
        import numpy as np
        import soundfile as sf
        velocidad = 1.15 if f.rata else 1.0
        audio = self.tts.generate(f.hablado, sid=0, speed=velocidad)
        destino.parent.mkdir(parents=True, exist_ok=True)
        tmp = destino.with_suffix(".raw.wav")
        sf.write(str(tmp), np.asarray(audio.samples), audio.sample_rate)
        # Más grave y ronca: baja el tono y añade un poco de saturación (aproximación para pruebas).
        filtro = "asetrate={sr}*0.86,aresample=24000,atempo=1.16,acompressor=threshold=-20dB:ratio=3,volume=1.4".format(
            sr=audio.sample_rate)
        if f.rata:
            filtro += ",volume=1.3"
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(tmp), "-af", filtro, "-ac", "1", str(destino)],
                       check=True)
        tmp.unlink()
        return destino
