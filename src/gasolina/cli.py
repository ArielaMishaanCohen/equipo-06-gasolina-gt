"""Entrypoints de línea de comandos.

  gasolina-extraer RUTA [--motor] [--preproc] [--estrategia]   (Modelos)
  gasolina-evaluar [--etiquetas] [--imagenes]                  (Modelos; STUB)
  gasolina-sync {descargar,subir-logs}                         (Producción)
  gasolina-api [--host] [--port]                               (Producción)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

EXTENSIONES = {".jpg", ".jpeg", ".png", ".heic", ".heif"}


def _imagenes(ruta: Path) -> list[Path]:
    if ruta.is_dir():
        return sorted(p for p in ruta.iterdir() if p.suffix.lower() in EXTENSIONES)
    return [ruta]


# ------------------------------------------------------------------ Modelos


def extraer(argv: list[str] | None = None) -> None:
    from gasolina.extraccion import extraer_precios

    p = argparse.ArgumentParser(prog="gasolina-extraer", description="Lee precios de foto(s).")
    p.add_argument("ruta", type=Path, help="imagen o carpeta con imágenes")
    p.add_argument("--motor", default="rapidocr")
    p.add_argument("--preproc", default="gris_clahe")
    p.add_argument("--estrategia", default="fusion", choices=["solo_A", "solo_B", "fusion"])
    p.add_argument("--segunda-pasada", action="store_true")
    a = p.parse_args(argv)
    if not a.ruta.exists():
        p.error(f"No existe: {a.ruta}")
    resultados = [
        extraer_precios(
            img,
            motor=a.motor,
            preproc=a.preproc,
            estrategia=a.estrategia,
            segunda_pasada=a.segunda_pasada,
        )
        for img in _imagenes(a.ruta)
    ]
    salida = resultados[0] if a.ruta.is_file() else resultados
    print(json.dumps(salida, indent=2, ensure_ascii=False, default=str))


def evaluar(argv: list[str] | None = None) -> None:
    """STUB: la implementa Modelos (sección 8.1.2). Por ahora solo reporta qué evaluaría."""
    p = argparse.ArgumentParser(prog="gasolina-evaluar", description="Evalúa contra etiquetas.")
    p.add_argument("--etiquetas", type=Path, default=Path("../datos/etiquetas.csv"))
    p.add_argument("--imagenes", type=Path, default=Path("../datos"))
    p.add_argument("--motor", default="rapidocr")
    p.add_argument("--preproc", default="gris_clahe")
    p.add_argument("--estrategia", default="fusion")
    a = p.parse_args(argv)
    filas = None
    if a.etiquetas.is_file():
        import pandas as pd

        filas = len(pd.read_csv(a.etiquetas))
    print(
        json.dumps(
            {
                "modo": "stub",
                "mensaje": "gasolina-evaluar todavía no está implementado (Modelos, 8.1.2).",
                "etiquetas": str(a.etiquetas),
                "etiquetas_existe": a.etiquetas.is_file(),
                "filas_etiquetas": filas,
                "imagenes": [p.name for p in _imagenes(a.imagenes)] if a.imagenes.exists() else [],
                "motor": a.motor,
                "preproc": a.preproc,
                "estrategia": a.estrategia,
                "metricas": {
                    "accuracy_precio": None,
                    "mae": None,
                    "pct_fotos_4_correctos": None,
                    "tiempo_ms_promedio": None,
                },
            },
            indent=2,
            ensure_ascii=False,
        )
    )


# ------------------------------------------------------------------ Producción


def sync(argv: list[str] | None = None) -> None:
    from gasolina import sync as _sync

    p = argparse.ArgumentParser(prog="gasolina-sync", description="Sincroniza con Databricks.")
    sub = p.add_subparsers(dest="accion", required=True)
    sub.add_parser("descargar", help="artifacts de oro -> ARTIFACTS_DIR")
    sub.add_parser("subir-logs", help="logs/*.jsonl -> bronce (api_logs)")
    a = p.parse_args(argv)
    sys.exit(_sync.main(a.accion))


def api(argv: list[str] | None = None) -> None:
    import uvicorn

    p = argparse.ArgumentParser(prog="gasolina-api", description="Levanta la API (FastAPI).")
    p.add_argument("--host", default=os.environ.get("HOST", "0.0.0.0"))
    p.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8000")))
    a = p.parse_args(argv)
    uvicorn.run("gasolina.api.app:app", host=a.host, port=a.port, log_level="info")


if __name__ == "__main__":  # pragma: no cover
    extraer()
