#!/usr/bin/env bash
# Prueba de usuario final: precio actual y predicción de super, regular y diésel.
# Uso:  BASE_URL=http://159.65.111.14:8006 bash tests/consultas_api.sh
#       (por defecto http://localhost:8006)
set -u
BASE_URL="${BASE_URL:-http://localhost:8006}"
FALLAS=0

consulta() {
  local titulo="$1" ruta="$2"
  echo
  echo "=== $titulo"
  echo "GET $BASE_URL$ruta"
  local codigo
  codigo=$(curl -s -o /tmp/consulta_api.json -w "%{http_code}" --max-time 20 "$BASE_URL$ruta")
  if command -v python3 >/dev/null; then
    python3 -m json.tool /tmp/consulta_api.json 2>/dev/null | head -40 || cat /tmp/consulta_api.json
  else
    cat /tmp/consulta_api.json
  fi
  echo "-> HTTP $codigo"
  [ "$codigo" = "200" ] || FALLAS=$((FALLAS + 1))
}

consulta "Estado del servicio" "/health"
consulta "Precio actual por combustible" "/precios/actual"
for c in super regular diesel; do
  consulta "Predicción de la semana siguiente: $c" "/prediccion?combustible=$c"
done
consulta "Histórico de diésel (oct-nov 2026, máximo 10)" "/precios?combustible=diesel&desde=2026-10-01&hasta=2026-11-30&limit=10"
consulta "Métricas del modelo vs. línea base" "/modelo/metricas"

echo
if [ "$FALLAS" -eq 0 ]; then echo "✅ Todas las consultas respondieron 200"; else echo "❌ $FALLAS consulta(s) fallaron"; fi
exit "$FALLAS"
