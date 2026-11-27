"""Montaje: ajusta las imágenes del resumen original a la nueva narración del mapache.

Cada frase nueva usa los planos del tramo del video original que cuenta (frase.fuente), sin los tramos
excluidos (autopromoción, pantalla final). Encima van las tarjetas, rótulos, sticker de censura y el
mapache; debajo, la voz nueva y, si existe, la música y los efectos del original sin su narrador.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from PIL import Image

from . import recursos
from .config import estilo
from .guion import Frase
from .limpieza import filtro_logo

FPS = 30


def duracion_audio(ruta: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(ruta)],
                         capture_output=True, text=True, check=True).stdout
    return float(out.strip())


def _restar(a: float, b: float, excluidos: list[dict]) -> list[tuple[float, float]]:
    partes = [(a, b)]
    for ex in excluidos:
        nuevas = []
        for s, e in partes:
            if ex["fin"] <= s or ex["inicio"] >= e:
                nuevas.append((s, e))
                continue
            if ex["inicio"] > s:
                nuevas.append((s, ex["inicio"]))
            if ex["fin"] < e:
                nuevas.append((ex["fin"], e))
        partes = nuevas
    return [(s, e) for s, e in partes if e - s > 0.3]


def elegir_planos(fuente: tuple[float, float], dur: float, cortes: list[dict],
                  excluidos: list[dict]) -> list[tuple[float, float]]:
    """Trozos (inicio, fin) del original que suman `dur` segundos, respetando el ritmo de corte.

    Reparte el tiempo entre los planos del tramo de forma pareja (ningún plano pasa de plano_s.max);
    si faltan imágenes, vuelve a usar los planos del tramo, como hacen los canales de referencia.
    """
    cfg = estilo("montaje")["plano_s"]
    a, b = fuente
    planos = []
    for p in cortes:
        s, e = max(p["inicio"], a), min(p["fin"], b)
        if e - s > 0.3:
            planos += _restar(s, e, excluidos)
    if not planos:  # tramo vacío: el plano válido más cercano
        validos = [x for p in cortes for x in _restar(p["inicio"], p["fin"], excluidos)]
        planos = [min(validos, key=lambda x: abs(x[0] - a))]
    largos = [min(e - s, cfg["max"]) for s, e in planos]
    if sum(largos) < dur:  # reciclaje de planos
        vueltas = int(dur // sum(largos)) + 1
        planos, largos = planos * vueltas, largos * vueltas
    n = max(1, round(dur / cfg["mediano"]))
    while len(planos) > n:  # sobran planos: se toman repartidos por todo el tramo
        idx = sorted({round(i * (len(planos) - 1) / (n - 1)) for i in range(n)}) if n > 1 else [len(planos) // 2]
        if sum(largos[i] for i in idx) >= dur:
            planos, largos = [planos[i] for i in idx], [largos[i] for i in idx]
            break
        n += 1  # los elegidos no alcanzan: se toma uno más
    lo, hi = 0.0, max(largos)  # reparto parejo: x_i = min(l_i, c) con suma = dur
    for _ in range(50):
        c = (lo + hi) / 2
        if sum(min(l, c) for l in largos) < dur:
            lo = c
        else:
            hi = c
    trozos = []
    for (s, e), l in zip(planos, largos):
        x = min(l, hi)
        if x >= 0.05:
            ini = s + (min(e - s, l) - x) / 2
            trozos.append((ini, ini + x))
    return trozos


def _render_base(video: Path, trozos, logo, tamano, destino: Path) -> None:
    W, H = tamano
    entradas = []
    for s, e in trozos:  # una entrada por trozo con búsqueda rápida, en vez de decodificar todo el video
        entradas += ["-ss", f"{s:.3f}", "-t", f"{e - s:.3f}", "-i", str(video)]
    partes = [f"[{i}:v]setpts=PTS-STARTPTS,scale={W}:{H},setsar=1,fps={FPS}[t{i}]" for i in range(len(trozos))]
    etiquetas = "".join(f"[t{i}]" for i in range(len(trozos)))
    kx, ky = W / _tam_origen(video)[0], H / _tam_origen(video)[1]
    logo_esc = {k: int(v * (kx if k in ("x", "w") else ky)) for k, v in logo.items() if k in "xywh"} if logo else None
    filtro = ";".join(partes) + f";{etiquetas}concat=n={len(trozos)}:v=1:a=0," \
             f"{filtro_logo(logo_esc)},format=yuv420p[v]"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", *entradas, "-filter_complex", filtro, "-map", "[v]",
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", str(destino)], check=True)


def _tam_origen(video: Path) -> tuple[int, int]:
    from .limpieza import tamano
    return tamano(video)


def _audio_frase(f: Frase, voz: Path, dur: float, trabajo: Path, fondo: Path | None, trozos) -> Path:
    """Voz + sonido de corte en la grosería + fondo del original (si se separó) bajo la voz."""
    cfg = estilo("montaje")
    salida = trabajo / f"audio_{f.id:03d}.wav"
    entradas = ["-i", str(voz)]
    cadena = ["[0:a]aresample=44100,aformat=channel_layouts=mono"]
    if f.groseria:
        corte = recursos.sonido_corte(trabajo / "corte.wav")
        ini = max(0.0, duracion_audio(voz) - cfg["groseria"]["dur_s"] * 0.8)
        cadena[0] += f",volume=enable='gte(t,{ini:.3f})':volume=0"  # la palabra queda cortada
        entradas += ["-i", str(corte)]
        ms = int(ini * 1000)
        cadena.append(f"[1:a]adelay={ms}|{ms},aresample=44100,aformat=channel_layouts=mono")
    filtro = ";".join(f"{c}[a{i}]" for i, c in enumerate(cadena))
    filtro += f";{''.join(f'[a{i}]' for i in range(len(cadena)))}amix=inputs={len(cadena)}:normalize=0," \
              f"apad=whole_dur={dur:.3f}[voz]"
    final = "[voz]"
    if fondo is not None:
        k = len(entradas) // 2
        entradas += ["-i", str(fondo)]
        trims = "".join(f"[{k}:a]atrim=start={s:.3f}:end={e:.3f},asetpts=PTS-STARTPTS[f{i}];"
                        for i, (s, e) in enumerate(trozos))
        filtro += ";" + trims + "".join(f"[f{i}]" for i in range(len(trozos))) + \
                  f"concat=n={len(trozos)}:v=0:a=1,aformat=channel_layouts=mono," \
                  f"volume={cfg['audio']['fondo_bajo_voz_db']}dB[fo];[voz][fo]amix=inputs=2:normalize=0:duration=first[s]"
        final = "[s]"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", *entradas, "-filter_complex", filtro, "-map", final,
                    "-t", f"{dur:.3f}", "-ac", "2", "-ar", "44100", str(salida)], check=True)
    return salida


def montar_frase(f: Frase, voz: Path, video: Path, cortes, excluidos, logo, tamano, trabajo: Path,
                 fondo: Path | None = None, elector=None, mapache: bool = False) -> Path:
    """Arma una frase. Con `elector` (cerebro.cortes.Elector) las tomas se eligen por contenido;
    sin él se usa el reparto por tiempo antiguo. El mapache solo se pone si `mapache` es True:
    hasta tener la animación real no se muestra (Jhon rechazó la imagen fija)."""
    cfg = estilo("montaje")
    W, H = tamano
    trabajo.mkdir(parents=True, exist_ok=True)
    dur = duracion_audio(voz) + (1.3 if f.pausa else 0.15)
    if elector is not None:
        fuentes = [tuple(x) for x in getattr(f, "fuentes", None) or [f.fuente]]
        trozos = elector.elegir(fuentes, f.hablado, dur, reservar=not getattr(f, "fuentes", None))
    else:
        trozos = elegir_planos(f.fuente, dur, cortes, excluidos)
    base = trabajo / f"base_{f.id:03d}.mp4"
    _render_base(video, trozos, logo, tamano, base)
    audio = _audio_frase(f, voz, dur, trabajo, fondo, trozos)

    entradas, filtros, etiqueta = [], [], "[0:v]"

    def poner(ruta: Path, inicio: float, fin: float, imagen: bool) -> None:
        nonlocal etiqueta
        entradas.extend(["-loop", "1", "-t", f"{dur:.3f}", "-i", str(ruta)] if imagen else ["-i", str(ruta)])
        k = entradas.count("-i")
        filtros.append(f"{etiqueta}[{k}:v]overlay=0:0:enable='between(t,{inicio:.2f},{fin:.2f})'[c{k}]")
        etiqueta = f"[c{k}]"

    if f.censura:
        s = recursos.sticker_censura(int(H * 0.8))
        lienzo = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        lienzo.alpha_composite(s, ((W - s.width) // 2, (H - s.height) // 2))
        ruta = trabajo / f"censura_{f.id:03d}.png"
        lienzo.save(ruta)
        poner(ruta, 0, dur, True)
    for texto, tipo in ((f.tarjeta, "tarjeta_tiempo"), (f.lugar, "tarjeta_lugar"), (f.rotulo, "rotulo")):
        if texto:
            ruta = trabajo / f"{tipo}_{f.id:03d}.png"
            recursos.tarjeta(texto, tamano, tipo).save(ruta)
            poner(ruta, 0, cfg[tipo]["duracion_s"], True)
    if f.gesto and mapache:
        # Plano completo del mapache reaccionando, en el remate de la frase (como los canales de
        # referencia: 1 a 3 s). La boca se sincroniza con el trozo de voz que cae en ese plano.
        from . import animacion
        largo = min(3.0, max(1.2, dur * 0.45))
        ini = max(0.0, dur - largo)
        trozo_voz = trabajo / f"voz_inserto_{f.id:03d}.wav"
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(voz), "-ss", f"{ini:.3f}", "-t", f"{largo:.3f}",
                        "-af", f"apad=whole_dur={largo:.3f}", str(trozo_voz)], check=True)
        fondo_img = trabajo / f"fondo_inserto_{f.id:03d}.jpg"
        s0 = trozos[-1][0] if trozos else 0
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-ss", f"{s0:.3f}", "-i", str(video), "-frames:v", "1",
                        str(fondo_img)], check=True)
        emocion = "groseria" if f.groseria else ("furioso" if f.rata else (f.gesto or f.emocion))
        clip = animacion.inserto(trozo_voz, emocion, tamano, trabajo / f"mapache_{f.id:03d}.mp4", fondo_img, semilla=f.id)
        entradas.extend(["-itsoffset", f"{ini:.3f}", "-i", str(clip)])
        k = entradas.count("-i")
        filtros.append(f"{etiqueta}[{k}:v]overlay=0:0:eof_action=pass:enable='between(t,{ini:.2f},{dur:.2f})'[c{k}]")
        etiqueta = f"[c{k}]"

    salida = trabajo / f"frase_{f.id:03d}.mp4"
    n_audio = 1 + entradas.count("-i")
    cmd = ["ffmpeg", "-loglevel", "error", "-y", "-i", str(base), *entradas, "-i", str(audio)]
    cmd += ["-filter_complex", ";".join(filtros), "-map", etiqueta] if filtros else ["-map", "0:v"]
    cmd += ["-map", f"{n_audio}:a", "-t", f"{dur:.3f}", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-pix_fmt", "yuv420p", "-r", str(FPS), "-c:a", "aac", "-b:a", "160k", "-ar", "44100", str(salida)]
    subprocess.run(cmd, check=True)
    (trabajo / f"frase_{f.id:03d}.json").write_text(json.dumps({"dur": dur, "trozos": trozos}), encoding="utf-8")
    return salida


def unir(partes: list[Path], destino: Path) -> Path:
    lista = destino.with_suffix(".txt")
    lista.write_text("".join(f"file '{p.resolve()}'\n" for p in partes), encoding="utf-8")
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lista),
                    "-c", "copy", "-movflags", "+faststart", str(destino)], check=True)
    return destino
