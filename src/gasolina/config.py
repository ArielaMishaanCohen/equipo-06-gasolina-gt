"""Configuración: config/config.yaml + variables de entorno (dueña: Producción).

Búsqueda de config.yaml: $GASOLINA_CONFIG -> <raíz del repo>/config/config.yaml ->
./config/config.yaml. Si no existe, se usan DEFAULTS (nada truena).

Variables de entorno (ver api/.env.example). Si hay un .env en el directorio actual o en la raíz
del repo, se carga SIN sobrescribir variables ya definidas. Una variable vacía cuenta como no
definida.
"""

from __future__ import annotations

import copy
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

RAIZ_REPO = Path(__file__).resolve().parents[2]

DEFAULTS: dict = {
    "equipo": {"numero": 6, "prefijo_s3": "equipo6"},
    "databricks": {
        "catalogo": "workspace",
        "esquemas": {"bronze": "equipo6_bronze", "silver": "equipo6_silver",
                     "gold": "equipo6_gold"},
    },
    "s3": {
        "gold": "s3://cc3105-au-869227452861-us-east-2-an/equipo6",
        "region": "us-east-2",
    },
    "tablas": {
        "gold": ["precio_semanal", "variacion_semanal", "features_modelo", "predicciones",
                 "metricas_modelo"],
    },
    "combustibles": ["super", "regular", "diesel"],
    "calidad": {"rango_precio": {"min": 20.0, "max": 60.0}, "confianza_minima": 0.5},
    "direccion": {"umbral_q": 0.10, "clases": ["sube", "baja", "se_mantiene"]},
    "extraccion": {"motor": "rapidocr", "preproc": "gris_clahe"},
    "api": {"puerto": 8006, "limit_default": 100, "limit_max": 1000, "oro_ttl_segundos": 300,
            "zona_horaria_utc": -6},
}


def _fusionar(base: dict, extra: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in (extra or {}).items():
        out[k] = _fusionar(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def ruta_config() -> Path | None:
    candidatos = []
    if os.environ.get("GASOLINA_CONFIG"):
        candidatos.append(Path(os.environ["GASOLINA_CONFIG"]))
    candidatos += [RAIZ_REPO / "config" / "config.yaml", Path.cwd() / "config" / "config.yaml"]
    return next((c for c in candidatos if c.is_file()), None)


@lru_cache(maxsize=1)
def cargar_config() -> dict:
    """config.yaml fusionado sobre DEFAULTS (siempre un dict completo)."""
    ruta = ruta_config()
    datos = yaml.safe_load(ruta.read_text(encoding="utf-8")) if ruta else {}
    return _fusionar(DEFAULTS, datos or {})


def cargar_dotenv() -> None:
    """Carga .env (si existe) sin sobrescribir variables ya definidas. Sin dependencias.
    GASOLINA_SIN_DOTENV=1 lo desactiva (lo usan los tests)."""
    if os.environ.get("GASOLINA_SIN_DOTENV"):
        return
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


def _env(nombre: str, default=None):
    valor = os.environ.get(nombre)
    return valor if valor not in (None, "") else default


@dataclass(frozen=True)
class Ajustes:
    # Databricks (sync de logs y plan B de lectura de Oro vía SQL warehouse)
    databricks_host: str | None
    databricks_token: str | None
    databricks_warehouse_id: str | None
    # Oro en S3 (lectura directa con deltalake y credenciales de solo lectura)
    oro_s3_prefix: str | None
    aws_access_key_id: str | None
    aws_secret_access_key: str | None
    aws_region: str
    # Locales
    oro_demo_dir: Path
    logs_dir: Path
    bronze_logs_path: str
    entorno: str
    puerto: int


def ajustes() -> Ajustes:
    """Lee las variables de entorno en cada llamada (no se cachea)."""
    cargar_dotenv()
    cfg = cargar_config()
    return Ajustes(
        databricks_host=_env("DATABRICKS_HOST"),
        databricks_token=_env("DATABRICKS_TOKEN"),
        databricks_warehouse_id=_env("DATABRICKS_WAREHOUSE_ID"),
        oro_s3_prefix=(_env("ORO_S3_PREFIX") or "").rstrip("/") or None,
        aws_access_key_id=_env("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=_env("AWS_SECRET_ACCESS_KEY"),
        aws_region=_env("AWS_REGION", cfg["s3"].get("region", "us-east-2")),
        oro_demo_dir=Path(_env("ORO_DEMO_DIR") or RAIZ_REPO / "artifacts_demo" / "oro"),
        logs_dir=Path(_env("LOGS_DIR", "./logs")),
        bronze_logs_path=_env("BRONZE_LOGS_PATH",
                              "/Volumes/workspace/equipo6_bronze/crudos/api_logs").rstrip("/"),
        entorno=_env("ENTORNO", "local"),
        puerto=int(_env("PUERTO", cfg["api"]["puerto"])),
    )
