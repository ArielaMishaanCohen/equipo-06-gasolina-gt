"""API de producción sobre la capa Oro (dueña: Producción). Contrato 5.5 del instructivo.

  GET /                   página web (static/index.html)
  GET /health             estado del servicio y de cada tabla Oro
  GET /precios/actual     último precio semanal por combustible
  GET /precios            histórico semanal con filtros (combustible, desde, hasta, limit, offset)
  GET /prediccion         predicción de la semana siguiente (?combustible=super opcional)
  GET /modelo/metricas    exactitud del modelo y de la línea base
  GET /docs               Swagger (FastAPI)

Las tablas se leen con gasolina.oro.LectorOro (S3 -> Databricks SQL -> demo). Cada petición se
registra en logs/consultas_YYYYMMDD.jsonl (endpoint, estado y latencia; sin datos personales).
"""

from __future__ import annotations

import json
import logging
import math
import time
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Literal

import pandas as pd
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse

from gasolina import __version__
from gasolina.config import ajustes, cargar_config
from gasolina.oro import LectorOro

log = logging.getLogger("gasolina.api")
STATIC = Path(__file__).parent / "static"
Combustible = Literal["super", "regular", "diesel"]


def _tz() -> timezone:
    return timezone(timedelta(hours=cargar_config()["api"].get("zona_horaria_utc", -6)))


def _limpio(v):
    """Valores de pandas/numpy -> JSON (NaN -> None, fechas -> ISO)."""
    if v is None:
        return None
    if isinstance(v, float) and math.isnan(v):
        return None
    if isinstance(v, (pd.Timestamp, datetime)):
        return v.isoformat()
    if isinstance(v, date):
        return v.isoformat()
    if hasattr(v, "item"):  # numpy
        return _limpio(v.item())
    if v is pd.NaT:
        return None
    return v


def _registros(df: pd.DataFrame) -> list[dict]:
    return [{k: _limpio(v) for k, v in fila.items()} for fila in df.to_dict(orient="records")]


def _fecha(valor: str | None, nombre: str) -> date | None:
    if valor is None:
        return None
    try:
        return date.fromisoformat(valor)
    except ValueError:
        raise HTTPException(400, f"'{nombre}' debe tener formato AAAA-MM-DD (recibí '{valor}').")


def crear_app() -> FastAPI:
    aj = ajustes()
    cfg = cargar_config()
    oro = LectorOro(aj, ttl=float(cfg["api"]["oro_ttl_segundos"]))
    limit_default = int(cfg["api"]["limit_default"])
    limit_max = int(cfg["api"]["limit_max"])

    app = FastAPI(
        title="Precio de la gasolina en Guatemala — Equipo 6",
        version=__version__,
        description=(
            "API sobre la capa Oro del pipeline medallón (S3 + Databricks). Devuelve precios "
            "semanales (martes a lunes) de super, regular y diésel y la predicción de si cada "
            "uno sube, baja o se mantiene la semana siguiente."
        ),
    )
    app.state.oro = oro
    log.info("API %s | entorno %s | fuentes de Oro: %s", __version__, aj.entorno, oro._fuentes())

    # ---------------------------------------------------------------- registro de consultas
    @app.middleware("http")
    async def registrar(request: Request, call_next):
        t0 = time.perf_counter()
        resp = await call_next(request)
        if request.url.path not in ("/", "/favicon.ico") and not request.url.path.startswith(
            ("/docs", "/openapi")
        ):
            linea = {
                "id": str(uuid.uuid4()),
                "timestamp": datetime.now(_tz()).isoformat(timespec="seconds"),
                "endpoint": request.url.path,
                "query": str(request.url.query),
                "status": resp.status_code,
                "latencia_ms": round((time.perf_counter() - t0) * 1000, 1),
                "entorno": aj.entorno,
            }
            try:
                aj.logs_dir.mkdir(parents=True, exist_ok=True)
                archivo = aj.logs_dir / f"consultas_{datetime.now(_tz()):%Y%m%d}.jsonl"
                with open(archivo, "a", encoding="utf-8") as f:
                    f.write(json.dumps(linea, ensure_ascii=False) + "\n")
            except OSError as e:  # nunca tumbar la respuesta por el log
                log.error("No se pudo escribir el log: %s", e)
        return resp

    # ---------------------------------------------------------------- endpoints
    @app.get("/", include_in_schema=False)
    def inicio():
        return FileResponse(STATIC / "index.html", media_type="text/html")

    @app.get("/health", summary="Estado del servicio")
    def health():
        tablas = oro.estado()
        fuentes = {t["fuente"] for t in tablas.values()}
        return {
            "status": "ok",
            "version": __version__,
            "fuente_oro": fuentes.pop() if len(fuentes) == 1 else "mixta",
            "tablas": tablas,
            "entorno": aj.entorno,
            "hora_servidor": datetime.now(_tz()).isoformat(timespec="seconds"),
        }

    @app.get("/precios/actual", summary="Último precio semanal por combustible")
    def precios_actual():
        df = oro.tabla("precio_semanal")
        if df.empty:
            raise HTTPException(404, "Todavía no hay precios en la capa Oro.")
        # Si una semana tiene fuente "fotos" y "mem", gana "fotos" (lo que leímos nosotros).
        df = df.assign(_pref=(df["fuente"] != "fotos").astype(int)) if "fuente" in df else df
        orden = ["combustible", "semana_inicio"] + (["_pref"] if "_pref" in df else [])
        asc = [True, False] + ([True] if "_pref" in df else [])
        ultimos = df.sort_values(orden, ascending=asc).groupby("combustible").head(1)
        cols = [c for c in ("combustible", "semana_inicio", "semana_fin", "precio_promedio",
                            "precio_min", "precio_max", "fuente") if c in ultimos]
        return {
            "semana_inicio": _limpio(ultimos["semana_inicio"].max()),
            "precios": _registros(ultimos[cols].sort_values("combustible")),
        }

    @app.get("/precios", summary="Histórico semanal con filtros")
    def precios(
        combustible: Combustible | None = Query(None, description="super, regular o diesel"),
        desde: str | None = Query(None, description="AAAA-MM-DD (semana_inicio >= desde)"),
        hasta: str | None = Query(None, description="AAAA-MM-DD (semana_inicio <= hasta)"),
        limit: int = Query(limit_default, ge=1, le=limit_max),
        offset: int = Query(0, ge=0),
    ):
        d, h = _fecha(desde, "desde"), _fecha(hasta, "hasta")
        if d and h and d > h:
            raise HTTPException(400, "'desde' no puede ser posterior a 'hasta'.")
        df = oro.tabla("precio_semanal")
        var = oro.tabla("variacion_semanal")
        if not var.empty:
            extra = [c for c in ("dif_q", "dif_pct", "direccion") if c in var]
            df = df.merge(var[["semana_inicio", "combustible", *extra]],
                          on=["semana_inicio", "combustible"], how="left")
        if combustible:
            df = df[df["combustible"] == combustible]
        if d:
            df = df[df["semana_inicio"] >= d]
        if h:
            df = df[df["semana_inicio"] <= h]
        df = df.sort_values(["semana_inicio", "combustible"])
        return {
            "total": len(df),
            "limit": limit,
            "offset": offset,
            "datos": _registros(df.iloc[offset: offset + limit]),
        }

    @app.get("/prediccion", summary="Predicción de la semana siguiente")
    def prediccion(combustible: Combustible | None = Query(None)):
        df = oro.tabla("predicciones")
        if df.empty:
            raise HTTPException(404, "Todavía no hay predicciones en la capa Oro.")
        if "fecha_generacion" in df:
            df = df.sort_values("fecha_generacion")
        ult = df.sort_values("semana_objetivo").groupby("combustible").tail(1)

        def fmt(f: dict) -> dict:
            return {
                "semana": _limpio(f.get("semana_objetivo")),
                "combustible": f.get("combustible"),
                "prediccion": f.get("prediccion"),
                "probabilidad": _limpio(f.get("probabilidad")),
                "prediccion_baseline": f.get("prediccion_baseline"),
                "modelo": f.get("modelo"),
                "version_modelo": _limpio(f.get("version_modelo")),
            }

        filas = [fmt(f) for f in ult.sort_values("combustible").to_dict(orient="records")]
        if combustible:
            una = [f for f in filas if f["combustible"] == combustible]
            if not una:
                raise HTTPException(404, f"No hay predicción para '{combustible}'.")
            return una[0]
        return {"semana": max(f["semana"] for f in filas), "predicciones": filas}

    @app.get("/modelo/metricas", summary="Exactitud del modelo frente a la línea base")
    def modelo_metricas():
        df = oro.tabla("metricas_modelo")
        if df.empty:
            raise HTTPException(404, "Todavía no hay métricas del modelo en la capa Oro.")
        if "es_champion" in df and df["es_champion"].astype(bool).any():
            df = df[df["es_champion"].astype(bool)]
        fila = df.sort_values("fecha_entrenamiento").iloc[-1].to_dict()
        return {k: _limpio(v) for k, v in fila.items()}

    return app


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
app = crear_app()
