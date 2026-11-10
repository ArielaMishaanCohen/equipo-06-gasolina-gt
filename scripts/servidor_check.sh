#!/usr/bin/env bash
# Revisión rápida del servidor. Guarda todo en ~/servidor_check.txt
# Uso: bash scripts/servidor_check.sh
SALIDA="$HOME/servidor_check.txt"
{
  sec() { echo; echo "===== $* ====="; }
  sec "Fecha"; date
  sec "whoami"; whoami
  sec "hostname"; hostname
  sec "/etc/os-release"; head -4 /etc/os-release 2>/dev/null
  sec "nproc"; nproc
  sec "free -h"; free -h
  sec "df -h /"; df -h /
  sec "which git python3 docker tmux"; for b in git python3 docker tmux curl uv; do printf '%-8s %s\n' "$b" "$(command -v $b || echo 'NO')"; done
  sec "python3 --version"; python3 --version 2>&1
  sec "docker ps"; docker ps 2>&1 | head -5
  sec "docker compose version"; docker compose version 2>&1 | head -1
  sec "groups"; groups
  sec "sudo -n true"; sudo -n true 2>/dev/null && echo "TENGO SUDO" || echo "SIN SUDO"
  sec "ss -tlnp"; ss -tlnp 2>/dev/null | head -20

  if docker ps >/dev/null 2>&1; then DOCKER="SÍ"
  elif command -v docker >/dev/null; then DOCKER="NO (existe pero sin permiso: pedir grupo docker)"
  else DOCKER="NO (no instalado)"; fi
  RAM=$(free -h 2>/dev/null | awk '/^Mem:/ {print $2 " total, " $7 " disponible"}')
  if ss -tln 2>/dev/null | awk '{print $4}' | grep -qE '[:.]8000$'; then P8000="NO"; else P8000="SÍ"; fi

  echo
  echo "=================== RESUMEN ==================="
  echo "DOCKER: $DOCKER"
  echo "RAM: $RAM"
  echo "PUERTO 8000 LIBRE: $P8000"
  echo "PYTHON: $(python3 --version 2>&1)"
  echo "==============================================="
} 2>&1 | tee "$SALIDA"
echo "(Guardado en $SALIDA)"
