"""Evaluación de la extracción contra la revisión manual (dueño: Modelos).

etiquetas.csv: foto,fecha,combustible,modalidad,ubicacion,precio_q_galon[,lectura]
  Una fila por precio legible a simple vista. `lectura` (opcional) = "a_simple_vista" |
  "con_esta_venta" (dígitos tapados por el marco, confirmados con total / galones).

Métricas (un precio es correcto si |pred - real| < 0.005):
  - pct_precios_correctos: correctos / precios etiquetados.
  - incorrectos: se leyó un valor distinto. no_encontrados: no se devolvió ese combustible.
  - sin_etiqueta: se devolvió un combustible que la revisión manual no pudo leer (no se cuenta
    como error ni acierto: no hay con qué compararlo).
"""

from __future__ import annotations

import csv
import time
from pathlib import Path

TOLERANCIA = 0.005


def cargar_etiquetas(ruta: str | Path) -> dict[str, dict[str, dict]]:
    """{foto: {combustible: {"precio": float, "lectura": str}}} (foto = nombre de archivo)."""
    out: dict[str, dict[str, dict]] = {}
    with open(ruta, newline="", encoding="utf-8") as f:
        for fila in csv.DictReader(f):
            foto = Path(fila["foto"]).name
            out.setdefault(foto, {})[fila["combustible"].strip().lower()] = {
                "precio": float(fila["precio_q_galon"]),
                "lectura": (fila.get("lectura") or "a_simple_vista").strip(),
            }
    return out


def comparar(resultados: dict[str, dict], etiquetas: dict[str, dict[str, dict]]) -> dict:
    """resultados: {foto: salida de extraer_precios}. Devuelve métricas globales y por foto."""
    por_foto, tot = [], {"etiquetados": 0, "correctos": 0, "incorrectos": 0,
                         "no_encontrados": 0, "sin_etiqueta": 0}
    por_lectura: dict[str, list[int]] = {}
    for foto, verdad in sorted(etiquetas.items()):
        r = resultados.get(foto)
        pred = {x["combustible"]: x["precio_q_galon"] for x in (r or {}).get("registros", [])}
        detalle = {}
        for c, v in verdad.items():
            tot["etiquetados"] += 1
            if c not in pred:
                estado = "no_encontrado"
                tot["no_encontrados"] += 1
            elif abs(pred[c] - v["precio"]) < TOLERANCIA:
                estado = "correcto"
                tot["correctos"] += 1
            else:
                estado = f"incorrecto ({pred[c]:.2f})"
                tot["incorrectos"] += 1
            acc = por_lectura.setdefault(v["lectura"], [0, 0])
            acc[0] += estado == "correcto"
            acc[1] += 1
            detalle[c] = {"real": v["precio"], "estado": estado}
        extra = sorted(set(pred) - set(verdad))
        tot["sin_etiqueta"] += len(extra)
        por_foto.append({"foto": foto, "detalle": detalle, "sin_etiqueta": extra,
                         "tiempo_ms": (r or {}).get("tiempo_ms")})
    n = tot["etiquetados"] or 1
    tiempos = [f["tiempo_ms"] for f in por_foto if f["tiempo_ms"] is not None]
    return {
        "metricas": {
            **tot,
            "pct_precios_correctos": round(100 * tot["correctos"] / n, 1),
            "pct_fotos_completas": round(100 * sum(
                all(d["estado"] == "correcto" for d in f["detalle"].values()) for f in por_foto
            ) / max(1, len(por_foto)), 1),
            "pct_por_lectura": {k: round(100 * a / b, 1) for k, (a, b) in por_lectura.items()},
            "tiempo_ms_promedio": round(sum(tiempos) / len(tiempos)) if tiempos else None,
        },
        "por_foto": por_foto,
    }


def evaluar_carpeta(etiquetas_csv: str | Path, imagenes: str | Path, **kwargs) -> dict:
    """Corre extraer_precios sobre las fotos etiquetadas (buscadas por nombre en `imagenes`,
    recursivo) y las compara con la revisión manual. kwargs van a extraer_precios."""
    from gasolina.extraccion import extraer_precios

    etiquetas = cargar_etiquetas(etiquetas_csv)
    rutas = {p.name: p for p in Path(imagenes).rglob("*") if p.name in etiquetas}
    t0 = time.perf_counter()
    resultados = {foto: extraer_precios(ruta, **kwargs) for foto, ruta in sorted(rutas.items())}
    out = comparar(resultados, etiquetas)
    out["metricas"]["fotos_evaluadas"] = len(resultados)
    out["metricas"]["fotos_no_encontradas"] = sorted(set(etiquetas) - set(rutas))
    out["metricas"]["segundos_total"] = round(time.perf_counter() - t0, 1)
    out["parametros"] = {k: v for k, v in kwargs.items()}
    return out
