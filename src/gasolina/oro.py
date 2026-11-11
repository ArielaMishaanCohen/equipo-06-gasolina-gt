"""Lectura de la capa Oro para la API (dueña: Producción).

Fuentes, en orden de preferencia (la primera que funcione):
  1. "s3": tablas Delta en ORO_S3_PREFIX/<tabla>/ leídas con deltalake y credenciales de solo
     lectura (AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY / AWS_REGION). Lo que pide el enunciado.
  2. "databricks": plan B, SELECT vía SQL warehouse (DATABRICKS_HOST, DATABRICKS_TOKEN,
     DATABRICKS_WAREHOUSE_ID) sobre <catalogo>.<esquema gold>.<tabla>.
  3. "demo": tablas Delta de ejemplo en artifacts_demo/oro/ (scripts/generar_oro_demo.py).

Cada tabla se guarda en memoria y se vuelve a leer después de `ttl` segundos, para no ir a S3 en
cada petición. /health reporta de qué fuente salió cada tabla.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field

import pandas as pd

from gasolina.config import Ajustes, cargar_config

log = logging.getLogger("gasolina.oro")

TABLAS_ORO = (
    "precio_semanal",
    "variacion_semanal",
    "features_modelo",
    "predicciones",
    "metricas_modelo",
)


@dataclass
class _Entrada:
    df: pd.DataFrame
    fuente: str
    leida_en: float
    error: str | None = None


@dataclass
class LectorOro:
    aj: Ajustes
    ttl: float = 300.0
    _cache: dict[str, _Entrada] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    # ------------------------------------------------------------ fuentes

    def _fuentes(self) -> list[str]:
        f = []
        if self.aj.oro_s3_prefix and self.aj.aws_access_key_id and self.aj.aws_secret_access_key:
            f.append("s3")
        if self.aj.databricks_host and self.aj.databricks_token and self.aj.databricks_warehouse_id:
            f.append("databricks")
        f.append("demo")
        return f

    def _leer_s3(self, tabla: str) -> pd.DataFrame:
        from deltalake import DeltaTable

        opciones = {
            "AWS_ACCESS_KEY_ID": self.aj.aws_access_key_id,
            "AWS_SECRET_ACCESS_KEY": self.aj.aws_secret_access_key,
            "AWS_REGION": self.aj.aws_region,
        }
        return DeltaTable(f"{self.aj.oro_s3_prefix}/{tabla}", storage_options=opciones).to_pandas()

    def _leer_databricks(self, tabla: str) -> pd.DataFrame:
        from databricks.sdk import WorkspaceClient

        cfg = cargar_config()["databricks"]
        nombre = f"{cfg['catalogo']}.{cfg['esquemas']['gold']}.{tabla}"
        w = WorkspaceClient(host=self.aj.databricks_host, token=self.aj.databricks_token,
                            auth_type="pat")
        r = w.statement_execution.execute_statement(
            statement=f"SELECT * FROM {nombre}",
            warehouse_id=self.aj.databricks_warehouse_id,
            wait_timeout="30s",
        )
        if r.status and r.status.error:
            raise RuntimeError(r.status.error.message)
        columnas = [c.name for c in r.manifest.schema.columns]
        filas = (r.result.data_array if r.result else None) or []
        return pd.DataFrame(filas, columns=columnas)

    def _leer_demo(self, tabla: str) -> pd.DataFrame:
        from deltalake import DeltaTable

        return DeltaTable(str(self.aj.oro_demo_dir / tabla)).to_pandas()

    # ------------------------------------------------------------ API pública

    def tabla(self, nombre: str) -> pd.DataFrame:
        """DataFrame de la tabla Oro (vacío si no se pudo leer de ninguna fuente)."""
        return self._entrada(nombre).df

    def _entrada(self, nombre: str) -> _Entrada:
        with self._lock:
            e = self._cache.get(nombre)
            if e and time.time() - e.leida_en < self.ttl:
                return e
        errores = []
        for fuente in self._fuentes():
            try:
                df = getattr(self, f"_leer_{fuente}")(nombre)
                e = _Entrada(_normalizar(df), fuente, time.time())
                break
            except Exception as ex:  # se intenta la siguiente fuente
                errores.append(f"{fuente}: {type(ex).__name__}: {str(ex)[:160]}")
        else:
            log.warning("No se pudo leer %s: %s", nombre, errores)
            e = _Entrada(pd.DataFrame(), "ninguna", time.time(), "; ".join(errores))
        if errores and e.fuente != "ninguna":
            log.warning("%s se leyó de %s tras fallar: %s", nombre, e.fuente, errores)
        with self._lock:
            self._cache[nombre] = e
        return e

    def estado(self) -> dict:
        out = {}
        for t in TABLAS_ORO:
            e = self._entrada(t)
            ultima = None
            for col in ("semana_inicio", "semana_objetivo", "fecha_entrenamiento"):
                if col in e.df.columns and not e.df.empty:
                    ultima = str(e.df[col].max())[:10]
                    break
            out[t] = {"fuente": e.fuente, "filas": len(e.df), "ultima": ultima,
                      **({"error": e.error} if e.error else {})}
        return out

    def fuente_principal(self) -> str:
        fuentes = {v["fuente"] for v in self.estado().values()}
        return fuentes.pop() if len(fuentes) == 1 else "mixta"

    def invalidar(self) -> None:
        with self._lock:
            self._cache.clear()


def _normalizar(df: pd.DataFrame) -> pd.DataFrame:
    """Fechas como date y números como float (la fuente "databricks" devuelve texto)."""
    df = df.copy()
    for col in df.columns:
        if col.startswith(("semana_", "fecha")) and col != "fecha_generacion":
            df[col] = pd.to_datetime(df[col], errors="coerce").dt.date
        elif col == "fecha_generacion":
            df[col] = pd.to_datetime(df[col], errors="coerce")
        elif df[col].dtype == object and set(df[col].dropna().astype(str).str.lower()) <= {
            "true", "false"} and df[col].notna().any():
            df[col] = df[col].astype(str).str.lower().map({"true": True, "false": False})
        elif df[col].dtype == object and col not in ("version_modelo", "mlflow_run_id"):
            conv = pd.to_numeric(df[col], errors="coerce")
            if conv.notna().sum() == df[col].notna().sum() and df[col].notna().any():
                df[col] = conv
    return df
