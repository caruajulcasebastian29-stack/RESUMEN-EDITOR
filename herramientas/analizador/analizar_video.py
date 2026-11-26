#!/usr/bin/env python3
"""
Analizador de videos de referencia — App 2 (RESUMEN-EDITOR).

Por cada video produce, en una carpeta propia:
  info.json            duración, resolución, fps
  cortes.json          cada corte medido sobre la imagen y la duración de cada plano
  audio_segundos.json  volumen por segundo (dBFS) y silencios medidos
  transcripcion.json   lo que se dice, por tramos de voz, con inicio y fin
  hojas/minuto_XX.jpg  un fotograma por plano, rotulado con su segundo, para mirarlos
  ficha.json           todas las medidas juntas
  resumen.md           lo mismo, legible

Uso:
  python3 analizar_video.py VIDEO [--salida DIR] [--idioma es]
  python3 analizar_video.py --lote CARPETA [--salida DIR]

Cada etapa guarda su resultado; si se corta, al volver a lanzarlo sigue donde quedó.
Nada sale de esta máquina: no se usa ningún servicio externo.
"""
import argparse, json, math, re, subprocess, sys, time
from pathlib import Path

AQUI = Path(__file__).resolve().parent
MODELOS = AQUI / "modelos"
WHISPER = MODELOS / "sherpa-onnx-whisper-turbo"
VAD = MODELOS / "silero_vad.onnx"
VIDEO_EXT = {".mp4", ".mkv", ".mov", ".webm", ".avi", ".m4v"}

UMBRAL_CORTE = 0.30      # sensibilidad de la detección de cambio de escena
SILENCIO_DB = -35        # por debajo de esto se considera silencio
SILENCIO_MIN = 0.30      # segundos mínimos para contar un silencio
FPS_MUESTRA = 2          # fotogramas por segundo que se extraen para elegir el de cada plano
MINIATURA = (400, 225)
COLUMNAS, FILAS = 5, 8   # 40 planos por hoja como máximo


def log(m):
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def mmss(t):
    t = max(0, t)
    return f"{int(t // 60):02d}:{int(t % 60):02d}"


def guardar(p, data):
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(p)


def leer(p):
    return json.loads(p.read_text(encoding="utf-8"))


# ------------------------------------------------------------------ etapas

def etapa_info(video, out):
    p = out / "info.json"
    if p.exists():
        return leer(p)
    r = run(["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(video)])
    d = json.loads(r.stdout)
    v = next((s for s in d["streams"] if s["codec_type"] == "video"), {})
    a = next((s for s in d["streams"] if s["codec_type"] == "audio"), None)
    num, den = (v.get("avg_frame_rate", "0/1").split("/") + ["1"])[:2]
    den = float(den) if float(den) else 1.0
    info = {
        "archivo": video.name,
        "duracion_s": round(float(d["format"]["duration"]), 2),
        "ancho": v.get("width"), "alto": v.get("height"),
        "fps": round(float(num) / den, 3),
        "tiene_audio": a is not None,
        "tamano_mb": round(int(d["format"].get("size", 0)) / 1e6, 1),
    }
    guardar(p, info)
    return info


def etapa_cortes(video, out, dur):
    p = out / "cortes.json"
    if p.exists():
        return leer(p)
    log("Midiendo cortes…")
    r = run(["ffmpeg", "-hide_banner", "-i", str(video), "-an",
             "-vf", f"scale=320:-2,select='gt(scene,{UMBRAL_CORTE})',showinfo",
             "-f", "null", "-"])
    cortes = sorted({round(float(x), 2) for x in re.findall(r"pts_time:([0-9.]+)", r.stderr)})
    bordes = [0.0] + [c for c in cortes if 0.2 < c < dur - 0.2] + [dur]
    planos = [{"n": i + 1, "inicio": round(a, 2), "fin": round(b, 2), "dur": round(b - a, 2)}
              for i, (a, b) in enumerate(zip(bordes[:-1], bordes[1:])) if b - a > 0.04]
    res = {"umbral": UMBRAL_CORTE, "cortes": bordes[1:-1], "planos": planos}
    guardar(p, res)
    return res


def etapa_fotogramas(video, out, planos):
    hojas = out / "hojas"
    marca = hojas / ".hecho"
    if marca.exists():
        return sorted(hojas.glob("minuto_*.jpg"))
    log("Extrayendo fotogramas…")
    tmp = out / "_frames"
    tmp.mkdir(exist_ok=True)
    if not any(tmp.glob("f_*.jpg")):
        # Solo se baja el tamaño; el encuadre en la miniatura lo hace PIL,
        # que admite cualquier proporción (horizontal, vertical, cuadrada).
        run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(video), "-an",
             "-vf", f"fps={FPS_MUESTRA},scale='min(640,iw)':-2",
             "-q:v", "4", str(tmp / "f_%06d.jpg")])
    frames = sorted(tmp.glob("f_*.jpg"))
    if not frames:
        return []

    def frame_en(t):
        return frames[min(len(frames) - 1, max(0, int(round(t * FPS_MUESTRA))))]

    from PIL import Image, ImageDraw, ImageFont
    try:
        fuente = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf", 18)
    except Exception:
        fuente = ImageFont.load_default()

    por_minuto = {}
    for pl in planos:
        por_minuto.setdefault(int(pl["inicio"] // 60), []).append(pl)

    hojas.mkdir(exist_ok=True)
    w, h = MINIATURA
    rot = 26
    cap = COLUMNAS * FILAS
    for minuto, lista in sorted(por_minuto.items()):
        for parte, k in enumerate(range(0, len(lista), cap)):
            trozo = lista[k:k + cap]
            filas = math.ceil(len(trozo) / COLUMNAS)
            hoja = Image.new("RGB", (COLUMNAS * w, filas * (h + rot)), (16, 16, 16))
            d = ImageDraw.Draw(hoja)
            for j, pl in enumerate(trozo):
                x, y = (j % COLUMNAS) * w, (j // COLUMNAS) * (h + rot)
                img = Image.open(frame_en(pl["inicio"] + pl["dur"] / 2)).convert("RGB")
                img.thumbnail((w, h))
                hoja.paste(img, (x + (w - img.width) // 2, y + rot + (h - img.height) // 2))
                d.text((x + 6, y + 3), f"{mmss(pl['inicio'])}  #{pl['n']}  {pl['dur']:.1f}s",
                       fill=(255, 210, 60), font=fuente)
            sufijo = "" if parte == 0 else f"_{parte + 1}"
            hoja.save(hojas / f"minuto_{minuto:02d}{sufijo}.jpg", quality=82)
    marca.write_text("ok")
    for f in frames:
        f.unlink()
    tmp.rmdir()
    return sorted(hojas.glob("minuto_*.jpg"))


def etapa_audio(video, out):
    wav = out / "audio16k.wav"
    p = out / "audio_segundos.json"
    if not wav.exists():
        log("Extrayendo audio…")
        run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(video),
             "-vn", "-ac", "1", "-ar", "16000", str(wav)])
    if p.exists():
        return wav, leer(p)
    log("Midiendo volumen y silencios…")
    import numpy as np, soundfile as sf
    a, sr = sf.read(str(wav), dtype="float32")
    db = []
    for i in range(int(math.ceil(len(a) / sr))):
        s = a[i * sr:(i + 1) * sr]
        rms = float(np.sqrt(np.mean(s ** 2))) if len(s) else 0.0
        db.append(round(20 * math.log10(rms) if rms > 1e-6 else -90.0, 1))
    r = run(["ffmpeg", "-hide_banner", "-i", str(wav), "-af",
             f"silencedetect=noise={SILENCIO_DB}dB:d={SILENCIO_MIN}", "-f", "null", "-"])
    ini = [float(x) for x in re.findall(r"silence_start: ([0-9.]+)", r.stderr)]
    fin = [float(x) for x in re.findall(r"silence_end: ([0-9.]+)", r.stderr)]
    sil = [{"inicio": round(s, 2), "fin": round(e, 2), "dur": round(e - s, 2)} for s, e in zip(ini, fin)]
    res = {"db_por_segundo": db, "silencios": sil, "umbral_db": SILENCIO_DB, "silencio_min_s": SILENCIO_MIN}
    guardar(p, res)
    return wav, res


def etapa_transcripcion(wav, out, idioma):
    p = out / "transcripcion.json"
    if p.exists():
        return leer(p)
    parcial = out / "transcripcion.parcial.json"
    import soundfile as sf, sherpa_onnx
    a, sr = sf.read(str(wav), dtype="float32")

    seg_p = out / "tramos_voz.json"
    if seg_p.exists():
        tramos = leer(seg_p)
    else:
        log("Detectando tramos de voz…")
        cfg = sherpa_onnx.VadModelConfig()
        cfg.silero_vad.model = str(VAD)
        cfg.silero_vad.min_silence_duration = 0.25
        cfg.silero_vad.min_speech_duration = 0.25
        cfg.silero_vad.max_speech_duration = 20
        cfg.sample_rate = sr
        vad = sherpa_onnx.VoiceActivityDetector(cfg, buffer_size_in_seconds=120)
        win = cfg.silero_vad.window_size
        tramos = []

        def vaciar():
            while not vad.empty():
                s = vad.front
                tramos.append([round(s.start / sr, 2), round((s.start + len(s.samples)) / sr, 2)])
                vad.pop()

        for i in range(0, len(a), win):
            vad.accept_waveform(a[i:i + win])
            vaciar()
        vad.flush()
        vaciar()
        guardar(seg_p, tramos)

    hechos = leer(parcial) if parcial.exists() else []
    if len(hechos) < len(tramos):
        log(f"Transcribiendo {len(tramos) - len(hechos)} de {len(tramos)} tramos de voz…")
        rec = sherpa_onnx.OfflineRecognizer.from_whisper(
            encoder=str(WHISPER / "turbo-encoder.int8.onnx"),
            decoder=str(WHISPER / "turbo-decoder.int8.onnx"),
            tokens=str(WHISPER / "turbo-tokens.txt"),
            language=idioma or "", task="transcribe", num_threads=2)
        for k in range(len(hechos), len(tramos)):
            s, e = tramos[k]
            st = rec.create_stream()
            st.accept_waveform(sr, a[int(s * sr):int(e * sr)])
            rec.decode_stream(st)
            hechos.append({"inicio": s, "fin": e, "texto": st.result.text.strip()})
            if k % 10 == 9 or k == len(tramos) - 1:
                guardar(parcial, hechos)
                log(f"  {k + 1}/{len(tramos)} tramos")
    guardar(p, hechos)
    if parcial.exists():
        parcial.unlink()
    return hechos


def etapa_ficha(out, info, cortes, audio, trans):
    dur = info["duracion_s"]
    mins = dur / 60 if dur else 1
    planos = cortes["planos"]
    durs = sorted(pl["dur"] for pl in planos) or [0]
    palabras = sum(len(t["texto"].split()) for t in trans)
    voz_s = sum(t["fin"] - t["inicio"] for t in trans)
    sil = audio["silencios"]
    db = [x for x in audio["db_por_segundo"] if x > -90]

    # Candidatos a clip de reacción: plano corto (1–7 s), no el primero, durante el cual
    # el narrador apenas habla. Es la firma medible de «se corta todo, entra un clip, vuelve».
    def voz_en(a, b):
        return sum(max(0.0, min(b, t["fin"]) - max(a, t["inicio"])) for t in trans)

    candidatos = []
    for pl in planos[1:]:
        if 1.0 <= pl["dur"] <= 7.0:
            frac = voz_en(pl["inicio"], pl["fin"]) / pl["dur"]
            if frac < 0.30:
                candidatos.append({"plano": pl["n"], "inicio": pl["inicio"], "en": mmss(pl["inicio"]),
                                   "dur": pl["dur"], "voz_narrador_pct": round(100 * frac)})

    por_min = []
    for m in range(int(math.ceil(mins))):
        a, b = m * 60, (m + 1) * 60
        por_min.append({
            "minuto": m,
            "cortes": sum(1 for c in cortes["cortes"] if a <= c < b),
            "palabras": sum(len(t["texto"].split()) for t in trans if a <= t["inicio"] < b),
            "silencios": sum(1 for s in sil if a <= s["inicio"] < b),
        })

    ficha = {
        "archivo": info["archivo"],
        "duracion": mmss(dur), "duracion_s": dur,
        "montaje": {
            "planos": len(planos),
            "cortes_por_minuto": round(len(cortes["cortes"]) / mins, 1),
            "plano_medio_s": round(sum(durs) / len(durs), 2),
            "plano_mediana_s": durs[len(durs) // 2],
            "plano_mas_corto_s": durs[0],
            "plano_mas_largo_s": durs[-1],
        },
        "narracion": {
            "palabras": palabras,
            "palabras_por_minuto": round(palabras / mins),
            "palabras_por_minuto_de_voz": round(palabras / (voz_s / 60)) if voz_s else 0,
            "segundos_con_voz": round(voz_s),
            "porcentaje_con_voz": round(100 * voz_s / dur) if dur else 0,
        },
        "audio": {
            "silencios": len(sil),
            "silencio_total_s": round(sum(s["dur"] for s in sil), 1),
            "silencio_mas_largo_s": max((s["dur"] for s in sil), default=0),
            "volumen_medio_db": round(sum(db) / len(db), 1) if db else None,
        },
        "candidatos_reaccion": candidatos,
        "por_minuto": por_min,
        "origen": {"montaje": "medido", "narracion": "transcrito con Whisper turbo", "audio": "medido",
                   "candidatos_reaccion": "medido; hay que confirmarlos mirando la hoja de fotogramas"},
    }
    guardar(out / "ficha.json", ficha)

    m, n, au = ficha["montaje"], ficha["narracion"], ficha["audio"]
    md = [f"# {info['archivo']}", "",
          f"Duración {ficha['duracion']} · {info.get('ancho')}×{info.get('alto')}", "",
          "## Montaje (medido)", "",
          f"- {m['planos']} planos, **{m['cortes_por_minuto']} cortes por minuto**",
          f"- Plano medio {m['plano_medio_s']} s (mediana {m['plano_mediana_s']} s), "
          f"del más corto {m['plano_mas_corto_s']} s al más largo {m['plano_mas_largo_s']} s", "",
          "## Narración (transcrita)", "",
          f"- {n['palabras']} palabras, **{n['palabras_por_minuto']} por minuto** "
          f"({n['palabras_por_minuto_de_voz']} contando solo el tiempo con voz)",
          f"- Hay voz el {n['porcentaje_con_voz']} % del tiempo", "",
          "## Audio (medido)", "",
          f"- {au['silencios']} silencios, {au['silencio_total_s']} s en total, "
          f"el más largo {au['silencio_mas_largo_s']} s",
          f"- Volumen medio {au['volumen_medio_db']} dBFS", "",
          "## Candidatos a clip de reacción (medido, falta confirmar mirando)", ""]
    md += ([f"- **{c['en']}** plano #{c['plano']}, {c['dur']} s, narrador hablando el {c['voz_narrador_pct']} %"
            for c in candidatos] or ["- Ninguno"])
    md += ["", "## Minuto a minuto", "",
          "| Min | Cortes | Palabras | Silencios |", "|---|---|---|---|"]
    md += [f"| {p['minuto']:02d} | {p['cortes']} | {p['palabras']} | {p['silencios']} |" for p in por_min]
    md += ["", "## Transcripción", ""]
    md += [f"**{mmss(t['inicio'])}** {t['texto']}" for t in trans]
    (out / "resumen.md").write_text("\n".join(md), encoding="utf-8")
    return ficha


# ------------------------------------------------------------------ principal

def analizar(video, salida_base, idioma):
    video = Path(video)
    out = Path(salida_base) / video.stem
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    log(f"== {video.name}")
    info = etapa_info(video, out)
    log(f"Duración {mmss(info['duracion_s'])}, {info['ancho']}×{info['alto']}")
    cortes = etapa_cortes(video, out, info["duracion_s"])
    log(f"{len(cortes['planos'])} planos")
    hojas = etapa_fotogramas(video, out, cortes["planos"])
    log(f"{len(hojas)} hojas de fotogramas")
    if info["tiene_audio"]:
        wav, audio = etapa_audio(video, out)
        trans = etapa_transcripcion(wav, out, idioma)
    else:
        audio, trans = {"db_por_segundo": [], "silencios": []}, []
    ficha = etapa_ficha(out, info, cortes, audio, trans)
    wav_p = out / "audio16k.wav"
    if wav_p.exists():
        wav_p.unlink()
    log(f"Listo en {time.time() - t0:.0f} s → {out}")
    return ficha


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video", nargs="?")
    ap.add_argument("--lote", help="carpeta con varios videos")
    ap.add_argument("--salida", default=str(AQUI / "resultados"))
    ap.add_argument("--idioma", default="es")
    g = ap.parse_args()
    for f in (WHISPER / "turbo-encoder.int8.onnx", VAD):
        if not f.exists():
            sys.exit(f"Falta el modelo {f}. Ejecuta instalar.sh primero.")
    if g.lote:
        vids = sorted(p for p in Path(g.lote).iterdir() if p.suffix.lower() in VIDEO_EXT)
        log(f"{len(vids)} videos en el lote")
        for v in vids:
            if (Path(g.salida) / v.stem / "ficha.json").exists():
                log(f"Ya analizado: {v.name}")
                continue
            analizar(v, g.salida, g.idioma)
    elif g.video:
        analizar(g.video, g.salida, g.idioma)
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
