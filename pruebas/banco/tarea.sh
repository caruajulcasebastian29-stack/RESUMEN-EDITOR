#!/usr/bin/env bash
# Tarea actual del banco: mapache 3D con LivePortrait (modo animales) en CPU, versión más natural:
# movimiento suavizado, intensidad normal (1.0) y la cara pegada sobre la imagen original a resolución completa.
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
# Movimiento más natural: se suavizan las plantillas (sin tirones cuadro a cuadro)
python - <<'PY'
import pickle, numpy as np, glob, os
from scipy.ndimage import gaussian_filter1d
def suave(ruta, sigma=1.6):
    d = pickle.load(open(ruta, "rb"))
    m = d["motion"]
    for k in ("exp", "t", "scale"):
        a = np.stack([x[k] for x in m]).astype(np.float32)
        a = gaussian_filter1d(a, sigma, axis=0, mode="nearest")
        for x, v in zip(m, a):
            x[k] = v
    clave = "R" if "R" in m[0] else "R_d"
    R = np.stack([x[clave] for x in m]).astype(np.float32)
    R = gaussian_filter1d(R, sigma, axis=0, mode="nearest")
    for x, r in zip(m, R):
        u, _, vt = np.linalg.svd(r[0]); x[clave] = (u @ vt)[None].astype(np.float32)
    destino = ruta.replace(".pkl", "_suave.pkl")
    pickle.dump(d, open(destino, "wb"))
    print("suavizado", os.path.basename(destino), len(m), "cuadros")
for n in ("talking", "laugh", "shy", "aggrieved", "open_lip"):
    suave(f"assets/examples/driving/{n}.pkl")
PY
cd $GITHUB_WORKSPACE
# Imagen con margen del mismo fondo, para que al girar la cabeza no aparezcan esquinas negras
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
      --flag_force_cpu --no_flag_use_half_precision -o "$GITHUB_WORKSPACE/$OUT/$1" ) 2>&1 | tail -6
}
animar 11_explicando talking_suave
animar 01_frente talking_suave
animar 09_furioso aggrieved_suave
animar 05_rostro_serio shy_suave
animar 01_frente laugh_suave
animar 11_explicando open_lip_suave
# hojas de contacto y un cuadro a tamaño real para revisar los dientes
for v in $(find $OUT -name "*.mp4" ! -name "*concat*"); do
  ffmpeg -loglevel error -y -i "$v" -vf "fps=4,scale=320:-2,tile=6x2" -frames:v 1 "${v%.mp4}_hoja.jpg"
  ffmpeg -loglevel error -y -ss 1.2 -i "$v" -frames:v 1 -q:v 2 "${v%.mp4}_cuadro.jpg"
done
ls -la $OUT/*/ 2>/dev/null
