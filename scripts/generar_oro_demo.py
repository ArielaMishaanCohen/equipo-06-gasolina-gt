#!/usr/bin/env python3
"""Genera tablas Oro de EJEMPLO (contrato 5.4) como Delta local en artifacts_demo/oro/.

Sirven para construir y probar la API sin Databricks. Los datos son sintéticos (origen "demo"):
la API los usa solo si no puede leer las tablas reales de S3 o de Databricks.

Uso:  python scripts/generar_oro_demo.py [--semanas 30] [--destino artifacts_demo/oro]
"""

from __future__ import annotations

import argparse
import shutil
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from deltalake import write_deltalake

COMBUSTIBLES = ("super", "regular", "diesel")
BASE = {"super": 33.0, "regular": 32.0, "diesel": 30.5}
UMBRAL = 0.10


def martes_de(d: date) -> date:
    return d - timedelta(days=(d.weekday() - 1) % 7)  # weekday(): lunes=0, martes=1


def direccion(dif: float | None) -> str | None:
    if dif is None or pd.isna(dif):
        return None
    return "sube" if dif > UMBRAL else "baja" if dif < -UMBRAL else "se_mantiene"


def generar(semanas: int, hoy: date, semilla: int = 6) -> dict[str, pd.DataFrame]:
    rng = np.random.default_rng(semilla)
    ultima = martes_de(hoy) - timedelta(days=7)  # última semana completa
    inicios = [ultima - timedelta(days=7 * i) for i in range(semanas)][::-1]
    choque = np.cumsum(rng.normal(0, 0.35, semanas))  # tendencia común (petróleo)

    filas = []
    for c in COMBUSTIBLES:
        propio = np.cumsum(rng.normal(0, 0.12, semanas))
        for i, s in enumerate(inicios):
            p = round(BASE[c] + choque[i] + propio[i], 2)
            filas.append({"semana_inicio": s, "semana_fin": s + timedelta(days=6),
                          "combustible": c, "precio_promedio": p,
                          "precio_min": round(p - abs(rng.normal(0, 0.1)), 2),
                          "precio_max": round(p + abs(rng.normal(0, 0.1)), 2),
                          "n_registros": int(rng.integers(1, 3)), "fuente": "demo"})
    precio = pd.DataFrame(filas)

    var = precio.sort_values(["combustible", "semana_inicio"]).copy()
    var["precio_anterior"] = var.groupby("combustible")["precio_promedio"].shift(1)
    var["dif_q"] = (var["precio_promedio"] - var["precio_anterior"]).round(2)
    var["dif_pct"] = (100 * var["dif_q"] / var["precio_anterior"]).round(2)
    var["direccion"] = var["dif_q"].map(direccion)
    var["umbral_q"] = UMBRAL
    var = var[["semana_inicio", "combustible", "precio_promedio", "precio_anterior", "dif_q",
               "dif_pct", "direccion", "umbral_q"]]

    feat = var.copy()
    g = feat.groupby("combustible")
    for k in range(1, 5):
        feat[f"var_q_{k}"] = g["dif_q"].shift(k - 1)
    feat["prom_movil_4"] = g["precio_promedio"].transform(lambda s: s.rolling(4).mean()).round(2)
    pivote = precio.pivot(index="semana_inicio", columns="combustible", values="precio_promedio")
    feat["dif_super_diesel"] = feat["semana_inicio"].map(
        (pivote["super"] - pivote["diesel"]).round(2))
    feat["direccion_actual"] = feat["direccion"]
    feat["wti_var_1"] = np.round(rng.normal(0, 1.5, len(feat)), 2)
    feat["subsidio_activo"] = feat["semana_inicio"].map(
        lambda s: int(date(2026, 4, 28) <= s <= date(2026, 7, 14)))
    feat["direccion_siguiente"] = g["direccion"].shift(-1)
    feat = feat[["semana_inicio", "combustible", "var_q_1", "var_q_2", "var_q_3", "var_q_4",
                 "prom_movil_4", "dif_super_diesel", "direccion_actual", "wti_var_1",
                 "subsidio_activo", "direccion_siguiente"]]

    generado = datetime.combine(hoy, datetime.min.time())
    objetivo = ultima + timedelta(days=7)
    preds = []
    for s in inicios[-6:] + [objetivo]:
        for c in COMBUSTIBLES:
            fila = var[(var.combustible == c) & (var.semana_inicio == s)]
            previa = var[(var.combustible == c) & (var.semana_inicio == s - timedelta(days=7))]
            real = fila["direccion"].iloc[0] if len(fila) else None
            base = previa["direccion"].iloc[0] if len(previa) else "se_mantiene"
            pred = real if (real and rng.random() < 0.6) else rng.choice(
                ["sube", "baja", "se_mantiene"])
            preds.append({"semana_objetivo": s, "combustible": c, "prediccion": str(pred),
                          "probabilidad": round(float(rng.uniform(0.45, 0.8)), 2),
                          "prediccion_baseline": base, "modelo": "regresion_logistica",
                          "version_modelo": "demo", "mlflow_run_id": "demo",
                          "fecha_generacion": generado, "direccion_real": real})
    pred = pd.DataFrame(preds)

    metricas = pd.DataFrame([{
        "fecha_entrenamiento": generado, "modelo": "regresion_logistica",
        "version_modelo": "demo", "accuracy_modelo": 0.58, "accuracy_baseline": 0.47,
        "f1_macro_modelo": 0.52, "f1_macro_baseline": 0.41, "n_semanas_test": 8,
        "supera_baseline": True, "mlflow_run_id": "demo", "es_champion": True}])

    tablas = {"precio_semanal": precio, "variacion_semanal": var, "features_modelo": feat,
              "predicciones": pred, "metricas_modelo": metricas}
    return {k: v.reset_index(drop=True) for k, v in tablas.items()}


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--semanas", type=int, default=30)
    p.add_argument("--destino", type=Path,
                   default=Path(__file__).resolve().parents[1] / "artifacts_demo" / "oro")
    p.add_argument("--hoy", type=date.fromisoformat, default=date.today())
    a = p.parse_args()
    for nombre, df in generar(a.semanas, a.hoy).items():
        ruta = a.destino / nombre
        shutil.rmtree(ruta, ignore_errors=True)
        ruta.parent.mkdir(parents=True, exist_ok=True)
        write_deltalake(str(ruta), df, mode="overwrite",
                        configuration={"delta.appendOnly": "false"},
                        description=f"DEMO (datos sintéticos) - gold.{nombre}")
        print(f"✓ {nombre}: {len(df)} filas -> {ruta}")


if __name__ == "__main__":
    main()
