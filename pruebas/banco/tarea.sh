#!/usr/bin/env bash
# Tarea actual del banco: mapache 3D con LivePortrait (modo animales) en CPU, versión 8.
# Problema de la versión 7: la plantilla giraba la cabeza y movía toda la cara; en un personaje de pelo
# estilizado eso estira el antifaz, corta el pelo de la oreja y hace saltar el fósforo de un lado al otro.
# Ahora: la cabeza NO gira ni se desplaza; solo se mueven la boca (A: boca+ojos, B: solo boca), el recorte
# es más grande para que entren las orejas, y el cuerpo «respira» moviendo la imagen entera (sin deformar).
# Cada clip pasa un control automático: cuánto cambia la imagen fuera de la boca respecto del cuadro 1.
set -u
OUT=salida/animacion; mkdir -p $OUT
python -m pip install -q --upgrade pip
python -m pip install -q torch torchvision --index-url https://download.pytorch.org/whl/cpu
git clone -q --depth 1 https://github.com/KlingTeam/LivePortrait.git /tmp/lp
cd /tmp/lp
grep -v -i "torch\|onnxruntime-gpu" requirements_base.txt > /tmp/req.txt 2>/dev/null || grep -v -i "torch\|onnxruntime-gpu" requirements.txt > /tmp/req.txt
# las versiones fijas del proyecto no existen para Python 3.12: se instalan los mismos paquetes sin fijar versión
sed -E 's/[=<>~].*$//' /tmp/req.txt | grep -v -E "^\s*$|^#|gradio" > /tmp/req2.txt
python -m pip install -q -r /tmp/req2.txt onnxruntime huggingface_hub requests 2>&1 | tail -5
python -c "import requests, cv2, tyro, imageio, skimage, scipy, yaml; print('dependencias ok')"
python - <<'PY'
from huggingface_hub import snapshot_download
snapshot_download("KwaiVGI/LivePortrait", local_dir="pretrained_weights", allow_patterns=["liveportrait_animals/*", "insightface/*", "liveportrait/base_models/*", "liveportrait/retargeting_models/*", "liveportrait/landmark.onnx"])
print("pesos listos")
PY
# Sin tarjeta gráfica: el operador compilado de X-Pose no existe; se usa su versión en PyTorch puro.
python - <<'PY'
p = "src/utils/dependencies/XPose/models/UniPose/ops/functions/ms_deform_attn_func.py"
s = open(p).read()
s = s.replace("import MultiScaleDeformableAttention as MSDA", "try:\n    import MultiScaleDeformableAttention as MSDA\nexcept Exception:\n    MSDA = None")
s += '''

if MSDA is None:
    class MSDeformAttnFunction:  # versión CPU
        @staticmethod
        def apply(value, shapes, level_start_index, sampling_locations, attention_weights, im2col_step):
            return ms_deform_attn_core_pytorch(value, shapes, sampling_locations, attention_weights)
'''
open(p, "w").write(s)
print("parche CPU aplicado")
PY
# Los embeddings de CLIP se guardaron en GPU: en CPU hay que leerlos con map_location; y se muestra el error real.
python - <<'PY'
p = "src/utils/animal_landmark_runner.py"
s = open(p).read()
s = "import io as _io, torch as _torch\n_torch.storage._load_from_bytes = lambda b: _torch.load(_io.BytesIO(b), map_location='cpu', weights_only=False)\n" + s
s = s.replace('        except Exception:\n            raise ValueError("Could not load clip embeddings', '        except Exception as _e:\n            raise ValueError(f"{_e!r} Could not load clip embeddings')
open(p, "w").write(s)
print("parche embeddings aplicado")
PY
export TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD=1
# Sin GPU: el recortador de animales no recibe la opción de CPU (falla del proyecto); se la damos.
python - <<'PY'
p = "src/utils/cropper.py"
s = open(p).read()
s = s.replace('flag_force_cpu = kwargs.get("flag_force_cpu", False)', 'flag_force_cpu = kwargs.get("flag_force_cpu", False) or not torch.cuda.is_available()')
s = s.replace('embeddings_cache_path=self.crop_cfg.xpose_embedding_cache_path,', 'embeddings_cache_path=self.crop_cfg.xpose_embedding_cache_path,\n                    cpu_only=(device == "cpu"),')
open(p, "w").write(s)
print("parche recortador CPU aplicado", s.count("cpu_only=(device"))
PY
# X-Pose tiene "cuda" escrito a mano en varias partes: se cambia por "cuda si hay, si no cpu".
python - <<'PY'
import pathlib, re
DEV = "('cuda' if __import__('torch').cuda.is_available() else 'cpu')"
n = 0
for f in pathlib.Path("src/utils/dependencies/XPose").rglob("*.py"):
    s = f.read_text()
    t = s.replace(".to('cuda')", f".to({DEV})").replace('.to("cuda")', f".to({DEV})").replace(".cuda()", f".to({DEV})")
    t = re.sub(r"device\s*=\s*['\"]cuda['\"]", f"device={DEV}", t)
    if t != s:
        f.write_text(t); n += 1
print("parche cuda->cpu en", n, "archivos")
PY
grep -rn "cuda" src/utils/dependencies/XPose --include=*.py | grep -v "is_available" | head -8
ls assets/examples/driving | head -40 > $GITHUB_WORKSPACE/$OUT/plantillas.txt
# Plantillas «solo boca»: cabeza quieta (giro, posición y tamaño del primer cuadro) y expresión solo en los
# puntos de la boca (y de los ojos en la variante A). Índices de LivePortrait: boca 6,12,14,17,19,20; ojos 11,13,15,16,18.
python - <<'PY'
import pickle, numpy as np, os
from scipy.ndimage import gaussian_filter1d
BOCA, OJOS = [6, 12, 14, 17, 19, 20], [11, 13, 15, 16, 18]
def plantilla(nombre, puntos, sufijo, sigma=1.2, fuerza=1.0):
    d = pickle.load(open(f"assets/examples/driving/{nombre}.pkl", "rb"))
    m = d["motion"]
    clave = "R" if "R" in m[0] else "R_d"
    exp = np.stack([x["exp"] for x in m]).astype(np.float32)          # (n, 1, 21, 3)
    exp = gaussian_filter1d(exp, sigma, axis=0, mode="nearest")
    base = exp[0].copy()
    nuevo = np.repeat(base[None], len(m), 0)
    nuevo[:, :, puntos, :] = base[:, puntos, :] + fuerza * (exp[:, :, puntos, :] - base[:, puntos, :])
    for k, x in enumerate(m):
        x["exp"] = nuevo[k]
        x[clave] = m[0][clave].copy()
        x["t"] = m[0]["t"].copy()
        x["scale"] = m[0]["scale"].copy()
    destino = f"assets/examples/driving/{nombre}_{sufijo}.pkl"
    pickle.dump(d, open(destino, "wb"))
    mov = np.abs(nuevo - base).max(axis=(0, 1, 3))
    print("plantilla", os.path.basename(destino), len(m), "cuadros; movimiento por punto:", np.round(mov, 3).tolist())
for n in ("talking", "laugh", "aggrieved", "open_lip"):
    plantilla(n, BOCA + OJOS, "A")
    plantilla(n, BOCA, "B")
PY
cd $GITHUB_WORKSPACE
# Imagen con margen del mismo fondo
mkdir -p /tmp/poses
python - <<'PY'
from PIL import Image
import numpy as np
for pose in ("01_frente", "05_rostro_serio", "09_furioso", "11_explicando"):
    im = Image.open(f"recursos/mapache3d/mapache-poses/{pose}.png").convert("RGB")
    a = np.array(im)
    borde = np.concatenate([a[:6].reshape(-1, 3), a[:, :6].reshape(-1, 3), a[:, -6:].reshape(-1, 3)])
    color = tuple(int(c) for c in np.median(borde, axis=0))
    W, H = im.size
    lienzo = Image.new("RGB", (int(W * 1.3), int(H * 1.3)), color)
    lienzo.paste(im, ((lienzo.width - W) // 2, (lienzo.height - H) // 2))
    lienzo.save(f"/tmp/poses/{pose}.png")
    print("margen", pose, color)
PY
animar() {  # pose plantilla
  echo "== $1 con $2"
  ( cd /tmp/lp && CUDA_VISIBLE_DEVICES="" timeout 2400 python inference_animals.py -s "/tmp/poses/$1.png" \
      -d assets/examples/driving/$2.pkl --driving_multiplier 1.0 --flag_stitching --flag_pasteback \
      --scale 2.9 --vy_ratio -0.05 --flag_force_cpu --no_flag_use_half_precision -o "$GITHUB_WORKSPACE/$OUT/$1" ) 2>&1 | tail -4
}
animar 11_explicando talking_A
animar 11_explicando talking_B
animar 01_frente talking_A
animar 09_furioso aggrieved_A
animar 01_frente laugh_A
animar 11_explicando open_lip_B
# respiración: la imagen entera se agranda y sube un poco (ciclo de 3,2 s); nada de la cara se deforma
for v in $(find $OUT -name "*.mp4" ! -name "*concat*" ! -name "*_vivo.mp4"); do
  ffmpeg -loglevel error -y -i "$v" -vf "scale=w='trunc(iw*(1.025+0.008*sin(2*PI*t/3.2))/2)*2':h=-2:eval=frame,crop=iw/1.035:ih/1.035:(iw-ow)/2:(ih-oh)/2+4*sin(2*PI*t/3.2),scale=trunc(iw/2)*2:trunc(ih/2)*2" \
    -c:v libx264 -crf 18 -preset veryfast -pix_fmt yuv420p "${v%.mp4}_vivo.mp4" || echo "respiracion fallo $v"
done
# control de calidad: cuánto cambia la imagen fuera de la boca respecto del primer cuadro
python - <<'PY'
import glob, json, subprocess, numpy as np
from PIL import Image
def cuadros(v):
    w, h = map(int, subprocess.run(["ffprobe","-v","error","-select_streams","v:0","-show_entries","stream=width,height",
                                     "-of","csv=p=0",v], capture_output=True, text=True).stdout.strip().split(","))
    raw = subprocess.run(["ffmpeg","-v","error","-i",v,"-f","rawvideo","-pix_fmt","gray","-"], capture_output=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(-1, h, w).astype(np.float32)
informe = {}
for v in sorted(glob.glob("salida/animacion/*/*.mp4")):
    if "concat" in v or "_vivo" in v:
        continue
    f = cuadros(v)
    d = np.abs(f - f[0]).mean(0)                    # cuánto cambia cada píxel en promedio
    ys, xs = np.where(d >= np.percentile(d, 99.3))  # la zona que más se mueve: la boca
    cy, cx = np.median(ys), np.median(xs)
    hy, hx = max(40, 1.6 * np.percentile(np.abs(ys - cy), 90)), max(60, 1.6 * np.percentile(np.abs(xs - cx), 90))
    fuera = np.ones_like(d, bool)
    fuera[int(max(0, cy - hy)):int(cy + hy), int(max(0, cx - hx)):int(cx + hx)] = False
    peor = float(np.percentile(np.abs(f - f[0])[:, fuera], 99.5))
    medio = float(d[fuera].mean())
    area = float((d > 6).mean() * 100)  # % de la imagen que se mueve: solo boca ≈ 1 %; en la versión 7 era 5–20 %
    ok = area < 2.5
    informe[v] = {"area_que_se_mueve_pct": round(area, 2), "cambio_fuera_de_la_boca_p995": round(peor, 1), "cambio_medio_fuera": round(medio, 2),
                  "zona_boca": [int(cx), int(cy), int(hx), int(hy)], "aprobado": ok}
    print(("APROBADO " if ok else "RECHAZADO"), v, informe[v])
    n = len(f); idx = np.linspace(0, n - 1, 10).astype(int)
    y0, y1 = int(max(0, cy - 4 * hy)), int(min(f.shape[1], cy + 2.2 * hy)); x0, x1 = int(max(0, cx - 3 * hx)), int(min(f.shape[2], cx + 3 * hx))
    color = subprocess.run(["ffmpeg","-v","error","-i",v,"-f","rawvideo","-pix_fmt","rgb24","-"], capture_output=True).stdout
    c = np.frombuffer(color, np.uint8).reshape(n, f.shape[1], f.shape[2], 3)
    tiras = [Image.fromarray(c[k, y0:y1, x0:x1]).resize((360, int(360 * (y1 - y0) / max(1, x1 - x0)))) for k in idx]
    hoja = Image.new("RGB", (360 * 5, tiras[0].height * 2))
    for k, t in enumerate(tiras):
        hoja.paste(t, ((k % 5) * 360, (k // 5) * t.height))
    hoja.save(v.replace(".mp4", "_cara.jpg"), quality=90)
json.dump(informe, open("salida/animacion/control_calidad.json", "w"), indent=1)
PY
# hojas de contacto y un cuadro a tamaño real
for v in $(find $OUT -name "*.mp4" ! -name "*concat*" ! -name "*_vivo.mp4"); do
  ffmpeg -loglevel error -y -i "$v" -vf "fps=4,scale=320:-2,tile=6x2" -frames:v 1 "${v%.mp4}_hoja.jpg"
  ffmpeg -loglevel error -y -ss 1.2 -i "$v" -frames:v 1 -q:v 2 "${v%.mp4}_cuadro.jpg"
done
ls -la $OUT/*/ 2>/dev/null
