#!/usr/bin/env bash
# Tarea actual del banco: animar las poses del mapache 3D con LivePortrait (modo animales) en CPU,
# y probar la voz genérica con variación de ritmo.
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
ls assets/examples/driving | head -30 > $GITHUB_WORKSPACE/$OUT/plantillas.txt
cd $GITHUB_WORKSPACE
for pose in 01_frente 05_rostro_serio 11_explicando 09_furioso; do
  for d in $(cd /tmp/lp/assets/examples/driving && ls *.pkl 2>/dev/null | grep -i -E "talk|wink|aggrieved|shake|open" | head -2; cd /tmp/lp/assets/examples/driving && ls *.mp4 | head -1); do
    echo "== $pose con $d"
    ( cd /tmp/lp && CUDA_VISIBLE_DEVICES="" timeout 1500 python inference_animals.py -s "$GITHUB_WORKSPACE/recursos/mapache3d/mapache-poses/$pose.png" \
        -d assets/examples/driving/$d --driving_multiplier 1.75 --no_flag_stitching --flag_force_cpu --no_flag_use_half_precision -o "$GITHUB_WORKSPACE/$OUT/$pose" ) 2>&1 | tail -15
  done
done
# hojas de contacto para revisar sin descargar videos
for v in $(find $OUT -name "*.mp4" ! -name "*concat*"); do
  ffmpeg -loglevel error -y -i "$v" -vf "fps=4,scale=256:-2,tile=6x2" -frames:v 1 "${v%.mp4}_hoja.jpg"
done
ls -la $OUT/*/ 2>/dev/null
