#!/usr/bin/env bash
# Lo que corre el banco de pruebas. Todo lo que deba conservarse va a ./salida
set -u
mkdir -p salida ~/modelos ~/.ollama/models

echo "== Maquina"; nproc; free -g; df -h . | tail -1

echo "== FFmpeg"
sudo apt-get -qq update >/dev/null && sudo apt-get -qq install -y ffmpeg >/dev/null && ffmpeg -version | head -1

echo "== Ollama"
curl -fsSL https://ollama.com/install.sh | sh >/dev/null 2>&1
sudo systemctl stop ollama 2>/dev/null || true
(OLLAMA_MODELS=$HOME/.ollama/models ollama serve > salida/ollama.log 2>&1 &)
for i in $(seq 1 30); do curl -s localhost:11434/api/version && break; sleep 1; done; echo

while read -r m; do
  [ -z "$m" ] && continue
  echo "== Descargando $m"; ollama pull "$m" 2>&1 | tail -1
done < pruebas/banco/modelos.txt
ollama list

echo "== Prueba de texto"
/usr/bin/time -f "%e s" curl -s localhost:11434/api/generate -d '{"model":"qwen3:4b","prompt":"En una sola frase y en espanol: que es un resumen de pelicula?","stream":false,"think":false}' | python3 -c "import sys,json;print(json.load(sys.stdin)['response'])"

if [ -f pruebas/banco/tarea.sh ]; then
  echo "== Tarea"
  bash pruebas/banco/tarea.sh
fi
echo "== Fin"
