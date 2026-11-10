"""Configuración: config/config.yaml + variables de entorno (dueña: Producción).

Orden de búsqueda de config.yaml:
  1. Variable de entorno GASOLINA_CONFIG.
  2. <raíz del repo>/config/config.yaml (instalación editable o corriendo desde el repo).
  3. ./config/config.yaml (directorio actual; así funciona dentro de Docker, WORKDIR /app).
Si no se encuentra, se usan valores por defecto (DEFAULTS) para que nada truene.

Variables de entorno (ver .env.example). Si existe un archivo .env en el directorio actual o en
la raíz del repo, se carga SIN sobrescribir variables ya definidas. Una variable vacía
(ej. "ARTIFACTS_DIR=") cuenta como no definida.
"""

from __future__ import annotations

import copy
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

# src/gasolina/config.py -> parents[2] = raíz del repo
RAIZ_REPO = Path(__file__).resolve().parents[2]

DEFAULTS: dict = {
    "databricks": {
        "catalogo": "workspace",
        "volumenes": {
            "crudos": "/Volumes/workspace/g6_bronce/crudos",
            "artifacts": "/Volumes/workspace/g6_oro/artifacts",
        },
        "rutas_bronce": {"api_logs": "/Volumes/workspace/g6_bronce/crudos/api_logs"},
    },
    "combustibles": ["diesel", "regular", "super", "vpower"],
    "precios": {"rango_valido": {"min": 20.0, "max": 60.0}},
    "reglas": {
        "super_menos_regular": 1.00,
        "vpower_menos_super": 0.50,
        "tolerancia": 0.05,
        "tolerancia_ruta_a": 0.02,
        "tolerancia_mem_pct": 15,
    },
    "extraccion": {
        "motor": "rapidocr",
        "preproc": "gris_clahe",
        "estrategia": "fusion",
        "segunda_pasada": False,
        "umbral_score": 0.7,
    },
    "forecast": {"tipo_cambio": 7.7},
    "api": {
        "max_mb": 15,
        "extensiones": [".jpg", ".jpeg", ".png", ".heic", ".heif"],
        "zona_horaria_utc": -6,
    },
    "monitoreo": {
        "umbrales": {
            "pct_score_bajo_max": 30,
            "drift_vs_mem_pct_max": 10,
            "ratio_mae_prod_vs_validacion_max": 2.0,
            "latencia_p95_ms_max": 5000,
        }
    },
}


def _fusionar(base: dict, extra: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in (extra or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _fusionar(out[k], v)
        else:
            out[k] = v
    return out


def ruta_config() -> Path | None:
    candidatos = []
    if os.environ.get("GASOLINA_CONFIG"):
        candidatos.append(Path(os.environ["GASOLINA_CONFIG"]))
    candidatos += [RAIZ_REPO / "config" / "config.yaml", Path.cwd() / "config" / "config.yaml"]
    for c in candidatos:
        if c.is_file():
            return c
    return None


@lru_cache(maxsize=1)
def cargar_config() -> dict:
    """Devuelve config.yaml fusionado sobre DEFAULTS (siempre un dict completo)."""
    ruta = ruta_config()
    datos = {}
    if ruta:
        with open(ruta, encoding="utf-8") as f:
            datos = yaml.safe_load(f) or {}
    return _fusionar(DEFAULTS, datos)


def cargar_dotenv() -> None:
    """Carga .env (si existe) sin sobrescribir variables ya definidas. Sin dependencias."""
    for ruta in (Path.cwd() / ".env", RAIZ_REPO / ".env"):
        if not ruta.is_file():
            continue
        for linea in ruta.read_text(encoding="utf-8").splitlines():
            linea = linea.strip()
            if not linea or linea.startswith("#") or "=" not in linea:
                continue
            clave, valor = linea.split("=", 1)
            clave = clave.strip().removeprefix("export ").strip()
            valor = valor.strip().strip('"').strip("'")
            if clave and not os.environ.get(clave):
                os.environ[clave] = valor
        return


def _env(nombre: str, default: str | None = None) -> str | None:
    valor = os.environ.get(nombre)
    return valor if valor not in (None, "") else default


def _primera_existente(*rutas: Path) -> Path:
    for r in rutas:
        if r.is_dir():
            return r
    return rutas[0]


@dataclass(frozen=True)
class Ajustes:
    databricks_host: str | None
    databricks_token: str | None
    gold_artifacts_path: str
    bronze_logs_path: str
    artifacts_dir: Path
    artifacts_demo_dir: Path
    logs_dir: Path
    imagen_docker: str | None
    entorno: str


def ajustes() -> Ajustes:
    """Lee las variables de entorno (se vuelve a leer en cada llamada, no se cachea)."""
    cargar_dotenv()
    cfg = cargar_config()
    vol = cfg["databricks"]["volumenes"]
    return Ajustes(
        databricks_host=_env("DATABRICKS_HOST"),
        databricks_token=_env("DATABRICKS_TOKEN"),
        gold_artifacts_path=_env("GOLD_ARTIFACTS_PATH", vol["artifacts"]).rstrip("/"),
        bronze_logs_path=_env(
            "BRONZE_LOGS_PATH", cfg["databricks"]["rutas_bronce"]["api_logs"]
        ).rstrip("/"),
        artifacts_dir=Path(_env("ARTIFACTS_DIR", "./artifacts")),
        artifacts_demo_dir=Path(
            _env("ARTIFACTS_DEMO_DIR")
            or _primera_existente(RAIZ_REPO / "artifacts_demo", Path.cwd() / "artifacts_demo")
        ),
        logs_dir=Path(_env("LOGS_DIR", "./logs")),
        imagen_docker=_env("IMAGEN_DOCKER"),
        entorno=_env("ENTORNO", "local"),
    )
