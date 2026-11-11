#!/usr/bin/env bash
# Despliegue de la API en el servidor (DigitalOcean).
# Uso:  bash scripts/deploy.sh [--sin-pull] [--modo docker|venv]
#   --sin-pull : no hace git pull (lo usa el @reboot del crontab)
#   --modo     : docker o venv. Si no se indica, usa docker si "docker ps" funciona.
set -uo pipefail

# --- Ir a la raíz del repo (funciona aunque se llame desde otra carpeta o desde cron) ---
cd "$(dirname "$0")/.." || exit 1
REPO="$(pwd)"

# --- Leer flags ---
HACER_PULL=1
MODO=""
while [ $# -gt 0 ]; do
  case "$1" in
    --sin-pull) HACER_PULL=0 ;;
    --modo) shift; MODO="${1:-}" ;;
    --modo=*) MODO="${1#*=}" ;;
    *) echo "Opción desconocida: $1"; exit 2 ;;
  esac
  shift
done

paso() { echo; echo "==> $*"; }

# --- Detectar el modo: docker si "docker ps" funciona, si no venv ---
if [ -z "$MODO" ]; then
  if docker ps >/dev/null 2>&1; then MODO=docker; else MODO=venv; fi
fi
echo "Modo de despliegue: $MODO (repo: $REPO)"

# --- 1. Traer la última versión del código ---
if [ "$HACER_PULL" = 1 ]; then
  paso "git pull"
  git pull --ff-only || echo "AVISO: git pull falló; sigo con el código que ya está."
fi

# --- 2. Carpetas que la API usa (son volúmenes en Docker) ---
paso "Creando logs/"
mkdir -p logs

# --- 3. .env: debe existir; agregamos ENTORNO y el UID/GID del usuario si faltan ---
if [ ! -f .env ]; then
  echo "AVISO: no existe .env (sin credenciales de Databricks). Creo uno vacío desde .env.example."
  cp .env.example .env
fi
grep -q '^ENTORNO=' .env || echo "ENTORNO=servidor" >> .env
grep -q '^APP_UID=' .env || echo "APP_UID=$(id -u)" >> .env
grep -q '^APP_GID=' .env || echo "APP_GID=$(id -g)" >> .env
chmod 600 .env
# Cargar .env en este shell (para IMAGEN_DOCKER y el modo venv)
set -a; . ./.env; set +a
PUERTO="${PUERTO:-8006}"   # puerto 80XX del equipo (se define en .env)

mostrar_log() {
  if [ "$MODO" = docker ]; then docker compose logs --tail 40 api; else tail -n 40 logs/api.log; fi
}

esperar_health() {
  # Espera hasta 90 s a que /health responda y muestra el JSON.
  paso "Esperando a que /health responda (máx. 90 s)"
  for _ in $(seq 1 45); do
    if RESP=$(python3 -c "import urllib.request;print(urllib.request.urlopen('http://localhost:$PUERTO/health',timeout=3).read().decode())" 2>/dev/null); then
      echo "$RESP" | python3 -m json.tool
      echo
      echo "✅ API arriba en http://$(hostname -I 2>/dev/null | awk '{print $1}'):$PUERTO"
      return 0
    fi
    sleep 2
  done
  echo "❌ /health no respondió en 90 s. Últimas 40 líneas del log:"
  mostrar_log
  exit 1
}

if [ "$MODO" = docker ]; then
  # --- 4D. Imagen: descargar de GHCR si IMAGEN_DOCKER está definida; si falla, construir ---
  CONSTRUIR=0
  if [ -n "${IMAGEN_DOCKER:-}" ]; then
    paso "docker compose pull ($IMAGEN_DOCKER)"
    docker compose pull api || { echo "AVISO: pull falló; construyo la imagen aquí."; CONSTRUIR=1; }
  else
    CONSTRUIR=1
  fi
  if [ "$CONSTRUIR" = 1 ]; then
    paso "docker compose build"
    docker compose build api || { echo "❌ No se pudo construir la imagen."; exit 1; }
  fi

  # --- 6D. Levantar (restart: unless-stopped => se levanta sola al encender el servidor) ---
  paso "docker compose up -d"
  docker compose up -d api || { echo "❌ docker compose up falló."; mostrar_log; exit 1; }
  docker compose ps
else
  # --- 4V. Entorno virtual de Python ---
  export LOGS_DIR="$REPO/logs" ENTORNO="${ENTORNO:-servidor}" PUERTO
  export PATH="$HOME/.local/bin:$PATH"
  # Un .venv a medias (sin pip ni uv) se borra y se vuelve a crear.
  if [ -d .venv ] && ! .venv/bin/python -m pip --version >/dev/null 2>&1 \
     && [ ! -f .venv/.creado_con_uv ]; then
    rm -rf .venv
  fi
  if [ ! -x .venv/bin/python ]; then
    paso "Creando .venv"
    if ! python3 -m venv .venv >/dev/null 2>&1; then
      # Sin python3-venv (y sin sudo para instalarlo): usar uv, que se instala en ~/.local/bin.
      rm -rf .venv
      echo "python3-venv no está disponible; uso uv (sin sudo)."
      if ! command -v uv >/dev/null; then
        curl -LsSf https://astral.sh/uv/install.sh | sh \
          || { echo "❌ No se pudo instalar uv."; exit 1; }
      fi
      uv venv -p python3 .venv || { echo "❌ No se pudo crear el venv con uv."; exit 1; }
      touch .venv/.creado_con_uv
    fi
  fi
  paso 'Instalando dependencias'
  if [ -f uv.lock ] && command -v uv >/dev/null; then
    # Entorno reproducible: versiones exactas de uv.lock (pyproject.toml + uv.lock).
    uv sync --frozen --extra api || { echo "❌ uv sync falló."; exit 1; }
  elif [ -f .venv/.creado_con_uv ]; then
    uv pip install -p .venv/bin/python -q -e ".[api]" || { echo "❌ uv pip install falló."; exit 1; }
  else
    .venv/bin/python -m pip install -q --upgrade pip
    .venv/bin/python -m pip install -q -e ".[api]" || { echo "❌ pip install falló."; exit 1; }
  fi

  # --- 6V. Detener la instancia anterior (api.pid) ---
  if [ -f api.pid ] && kill -0 "$(cat api.pid)" 2>/dev/null; then
    paso "Deteniendo la API anterior (PID $(cat api.pid))"
    kill "$(cat api.pid)"; sleep 2
    kill -0 "$(cat api.pid)" 2>/dev/null && kill -9 "$(cat api.pid)"
  fi

  # --- 7V. Arrancar en segundo plano y guardar el PID ---
  paso "Arrancando gasolina-api con nohup"
  nohup .venv/bin/gasolina-api > logs/api.log 2>&1 &
  echo $! > api.pid
  echo "PID: $(cat api.pid)"

  # --- 8V. @reboot en crontab para que se levante sola al encender el servidor ---
  LINEA="@reboot cd $REPO && bash scripts/deploy.sh --sin-pull --modo venv >> logs/deploy.log 2>&1"
  if ! crontab -l 2>/dev/null | grep -qF "deploy.sh --sin-pull"; then
    paso "Instalando @reboot en crontab"
    (crontab -l 2>/dev/null; echo "$LINEA") | crontab - && echo "OK: $LINEA"
  fi
fi

esperar_health
