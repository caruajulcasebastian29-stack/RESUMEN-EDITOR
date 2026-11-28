"""Componer: solo la boca sale de la animación; el resto (ojos, antifaz, orejas, fósforo) es la imagen original."""
import subprocess, sys, json
import numpy as np, cv2
from PIL import Image

def leer(v):
    w, h = map(int, subprocess.run(["ffprobe","-v","error","-select_streams","v:0","-show_entries","stream=width,height","-of","csv=p=0",v],capture_output=True,text=True).stdout.strip().split(","))
    raw = subprocess.run(["ffmpeg","-v","error","-i",v,"-f","rawvideo","-pix_fmt","rgb24","-"],capture_output=True).stdout
    return np.frombuffer(raw,np.uint8).reshape(-1,h,w,3)

def fuente(pose, w, h):
    im = Image.open(pose).convert("RGB"); a = np.array(im)
    borde = np.concatenate([a[:6].reshape(-1,3), a[:, :6].reshape(-1,3), a[:, -6:].reshape(-1,3)])
    color = tuple(int(c) for c in np.median(borde, axis=0))
    W, H = im.size
    lienzo = Image.new("RGB", (int(W*1.3), int(H*1.3)), color)
    lienzo.paste(im, ((lienzo.width-W)//2, (lienzo.height-H)//2))
    return np.array(lienzo.resize((w, h), Image.LANCZOS))

def _fosforo(img):
    hsv = cv2.cvtColor(img, cv2.COLOR_RGB2HSV)
    return ((hsv[..., 0] >= 8) & (hsv[..., 0] <= 30) & (hsv[..., 1] > 70) & (hsv[..., 2] > 110)).astype(np.uint8)


def mascara(G, S):
    d = np.abs(G.astype(np.float32) - G[:1].astype(np.float32)).mean(axis=(0, 3))
    d = cv2.GaussianBlur(d, (0, 0), 4)
    m = (d > max(10.0, np.percentile(d, 99.7) * 0.45)).astype(np.uint8)
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (25, 25)))
    n, lab, est, _ = cv2.connectedComponentsWithStats(m)
    if n <= 1:
        return np.zeros(d.shape, np.float32), None, np.zeros(d.shape, np.uint8)
    k = 1 + int(np.argmax(est[1:, cv2.CC_STAT_AREA]))
    boca = (lab == k).astype(np.uint8)
    boca = cv2.dilate(boca, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (19, 19)))
    x, y, w, h = cv2.boundingRect(boca)
    # el fósforo (tono anaranjado/beige) cerca de la boca se queda quieto: viene de la imagen original
    fos = _fosforo(S)
    zona = np.zeros_like(fos); zona[max(0, y-60):y+h+60, max(0, x-120):x+w+120] = 1
    fos = cv2.dilate(fos * zona, np.ones((7, 7), np.uint8))
    boca = boca * (1 - fos)
    M = cv2.GaussianBlur(boca.astype(np.float32), (0, 0), 6)
    return np.clip(M * 1.2, 0, 1), (x, y, w, h), zona

if __name__ == "__main__":
    v, pose, salida = sys.argv[1:4]
    G = leer(v); S = fuente(pose, G.shape[2], G.shape[1])
    M, caja, zona = mascara(G, S)
    out = np.empty_like(G)
    for i, g in enumerate(G):
        # si en la animación el fósforo se movió, ese pedazo también vuelve a la imagen original
        fg = cv2.dilate(_fosforo(g) * zona, np.ones((9, 9), np.uint8)).astype(np.float32)
        Mi = (M * (1 - cv2.GaussianBlur(fg, (0, 0), 2)))[..., None]
        out[i] = (S.astype(np.float32) * (1 - Mi) + g.astype(np.float32) * Mi).astype(np.uint8)
    p = subprocess.Popen(["ffmpeg","-v","error","-y","-f","rawvideo","-pix_fmt","rgb24","-s",f"{G.shape[2]}x{G.shape[1]}","-r","25","-i","-",
                          "-c:v","libx264","-crf","17","-preset","veryfast","-pix_fmt","yuv420p",salida], stdin=subprocess.PIPE)
    p.stdin.write(out.tobytes()); p.stdin.close(); p.wait()
    area = float((np.abs(out.astype(np.float32) - out[:1].astype(np.float32)).mean(axis=(0, 3)) > 6).mean() * 100)
    print(json.dumps({"video": v, "caja_boca": caja, "area_que_se_mueve_pct": round(area, 2)}))
