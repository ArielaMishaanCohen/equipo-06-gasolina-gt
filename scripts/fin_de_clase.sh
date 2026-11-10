#!/usr/bin/env bash
# Al final de cada clase: sube los logs a bronce y muestra el estado de la API.
# Uso: bash scripts/fin_de_clase.sh
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
PUERTO="${PUERTO:-8000}"

if docker compose ps --status running api 2>/dev/null | grep -q api; then MODO=docker; else MODO=venv; fi
echo "Modo: $MODO"

echo; echo "==> Subiendo logs a Databricks (bronce/api_logs)"
if [ "$MODO" = docker ]; then
  docker compose run --rm --no-deps api gasolina-sync subir-logs || echo "AVISO: la subida falló."
else
  (set -a; [ -f .env ] && . ./.env; set +a
   LOGS_DIR="$(pwd)/logs" .venv/bin/gasolina-sync subir-logs) || echo "AVISO: la subida falló."
fi

echo; echo "==> Estado de la API"
python3 -c "import urllib.request,json;h=json.load(urllib.request.urlopen('http://localhost:$PUERTO/health',timeout=5));print(f\"status={h['status']} version={h['version']} artifacts={h['origen_artifacts']} modo={h['modo_extraccion']}\")" \
  || echo "❌ La API no responde en el puerto $PUERTO"
[ "$MODO" = docker ] && docker compose ps

HOY=$(TZ=America/Guatemala date +%Y%m%d)
ARCHIVO="logs/predicciones_$HOY.jsonl"
N=0; [ -f "$ARCHIVO" ] && N=$(wc -l < "$ARCHIVO" | tr -d ' ')
echo; echo "==> Peticiones a /extraer hoy ($HOY): $N"

echo
echo "Recordatorio: NO hace falta apagar nada. La API se levanta sola cuando el profesor"
echo "encienda el servidor (Docker: restart unless-stopped; venv: @reboot en crontab)."
