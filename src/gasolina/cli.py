"""Entrypoints de línea de comandos.

  gasolina-extraer RUTA [--motor] [--preproc]                  (Modelos)
  gasolina-evaluar [--etiquetas] [--imagenes] [--estrategia]    (Modelos)
  gasolina-sync subir-logs                                     (Producción)
  gasolina-api [--host] [--port]                               (Producción; puerto de PUERTO)
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
    a = p.parse_args(argv)
    if not a.ruta.exists():
        p.error(f"No existe: {a.ruta}")
    resultados = [
        extraer_precios(img, motor=a.motor, preproc=a.preproc)
        for img in _imagenes(a.ruta)
    ]
    salida = resultados[0] if a.ruta.is_file() else resultados
    print(json.dumps(salida, indent=2, ensure_ascii=False, default=str))


def evaluar(argv: list[str] | None = None) -> None:
    """% de precios correctos contra la revisión manual (datos/etiquetas.csv)."""
    from gasolina.evaluacion import elegir_configuracion, evaluar_carpeta
    from gasolina.ocr import PREPROCS

    p = argparse.ArgumentParser(prog="gasolina-evaluar", description="Evalúa contra etiquetas.")
    p.add_argument("--etiquetas", type=Path, default=Path("../datos/etiquetas.csv"))
    p.add_argument("--imagenes", type=Path, default=Path("../datos"))
    p.add_argument("--motor", default="rapidocr")
    p.add_argument("--preproc", default="gris_clahe")
    p.add_argument("--estrategia", default="fusion", choices=["fusion", "solo_B"])
    p.add_argument("--sin-segunda-pasada", action="store_true")
    p.add_argument("--detalle", action="store_true", help="incluir el resultado por foto")
    p.add_argument("--comparar-preprocs", action="store_true",
                   help="evaluar los 4 preprocesamientos")
    p.add_argument("--salida", type=Path, help="guardar el resultado completo en JSON")
    a = p.parse_args(argv)
    if not a.etiquetas.is_file():
        p.error(f"No existe {a.etiquetas}")
    corridas = [evaluar_carpeta(
        a.etiquetas, a.imagenes, motor=a.motor, preproc=preproc,
        estrategia=a.estrategia, segunda_pasada=not a.sin_segunda_pasada,
    ) for preproc in (PREPROCS if a.comparar_preprocs else [a.preproc])]
    if a.comparar_preprocs:
        try:
            ganador = elegir_configuracion(corridas)["parametros"]
            pendiente = None
        except ValueError as exc:
            ganador, pendiente = None, str(exc)
        out = {"corridas": corridas, "configuracion_recomendada": ganador,
               "pendiente": pendiente}
    else:
        out = corridas[0]
    if a.salida:
        a.salida.parent.mkdir(parents=True, exist_ok=True)
        a.salida.write_text(json.dumps(out, indent=2, ensure_ascii=False, default=str),
                            encoding="utf-8")
    if not a.detalle:
        for corrida in corridas:
            corrida.pop("por_foto")
    print(json.dumps(out, indent=2, ensure_ascii=False, default=str))


# ------------------------------------------------------------------ Producción


def sync(argv: list[str] | None = None) -> None:
    from gasolina import sync as _sync

    p = argparse.ArgumentParser(prog="gasolina-sync", description="Sincroniza con Databricks.")
    sub = p.add_subparsers(dest="accion", required=True)
    sub.add_parser("subir-logs", help="logs/*.jsonl -> bronce (api_logs)")
    a = p.parse_args(argv)
    sys.exit(_sync.main(a.accion))


def api(argv: list[str] | None = None) -> None:
    import uvicorn

    from gasolina.config import ajustes

    p = argparse.ArgumentParser(prog="gasolina-api", description="Levanta la API (FastAPI).")
    p.add_argument("--host", default=os.environ.get("HOST", "0.0.0.0"))
    p.add_argument("--port", type=int, default=ajustes().puerto)
    a = p.parse_args(argv)
    uvicorn.run("gasolina.api.app:app", host=a.host, port=a.port, log_level="info")


if __name__ == "__main__":  # pragma: no cover
    extraer()
