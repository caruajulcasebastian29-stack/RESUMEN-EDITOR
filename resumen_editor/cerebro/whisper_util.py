"""Ayudas para transcribir con Whisper (sherpa-onnx): decodificar un tramo, detectar y reparar
las frases que Whisper repite en bucle, y buscar el punto más callado para partir tramos largos.
(Sacadas del analizador original para que el cerebro no dependa de él.)"""
import re

TOKENS_POR_SEGUNDO = 15  # techo de texto por segundo de audio (el valor por defecto, 6, se queda corto)


def tiene_bucle(txt, n_min=3):
    """Whisper a veces se atasca repitiendo la misma frase. Detecta 3+ palabras repetidas seguidas."""
    w = [re.sub(r"[^\wáéíóúüñ]", "", x) for x in txt.lower().split()]
    for n in range(n_min, 13):
        for i in range(len(w) - 2 * n + 1):
            if w[i:i + n] == w[i + n:i + 2 * n]:
                return True
    # misma frase larga repetida con una palabra en medio («… aceptó y se ha enterado … aceptó»)
    for n in range(5, 13):
        for i in range(len(w) - 2 * n):
            if w[i:i + n] == w[i + n + 1:i + 2 * n + 1]:
                return True
    return False


def quitar_bucle(txt, n_min=3):
    """Corta el texto donde empieza la primera repetición: una vez que Whisper entra
    en bucle, lo que sigue en ese tramo ya no es fiable."""
    w = txt.split()
    v = [re.sub(r"[^\wáéíóúüñ]", "", x.lower()) for x in w]
    corte = None
    for n in range(n_min, 13):
        for g in ((0, 1) if n >= 5 else (0,)):
            for i in range(len(v) - 2 * n - g + 1):
                if v[i:i + n] == v[i + n + g:i + 2 * n + g]:
                    if corte is None or i + n < corte:
                        corte = i + n
                    break
    return " ".join(w[:corte]) + " […]" if corte else txt


def decodificar(rec, a, sr, s, e):
    st = rec.create_stream()
    # Por defecto Whisper corta en 6 piezas de texto por segundo; un narrador
    # de más de 200 palabras por minuto lo supera y la frase queda incompleta.
    st.set_option("max_tokens_per_second", str(TOKENS_POR_SEGUNDO))
    st.accept_waveform(sr, a[int(s * sr):int(e * sr)])
    rec.decode_stream(st)
    return st.result.text.strip()


def punto_callado(a, sr, ini, fin, obj, ventana=0.5):
    import numpy as np
    a0, b0 = max(ini, obj - ventana), min(fin, obj + ventana)
    tr = a[int(a0 * sr):int(b0 * sr)]
    if len(tr) < 320:
        return obj
    marco = 160
    en = [float(np.sqrt(np.mean(tr[i * marco:(i + 1) * marco] ** 2))) for i in range(len(tr) // marco)]
    return round(a0 + (en.index(min(en)) * marco) / sr, 2)


def reparar_bucles(rec, a, sr, hechos):
    """Vuelve a transcribir en dos mitades los tramos con frases repetidas en bucle.
    Si la repetición sigue, la quita y marca el tramo como dudoso."""
    n = 0
    for h in hechos:
        if not tiene_bucle(h["texto"]):
            continue
        s, e = h["inicio"], h["fin"]
        m = punto_callado(a, sr, s, e, (s + e) / 2, ventana=1.0)
        texto = (decodificar(rec, a, sr, s, m) + " " + decodificar(rec, a, sr, m, e)).strip()
        if tiene_bucle(texto):
            texto = quitar_bucle(texto)
            h["dudoso"] = True
        h["texto"] = texto
        h["reparado"] = True
        n += 1
    return n
