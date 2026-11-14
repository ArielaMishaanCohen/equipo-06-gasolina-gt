"""Clasificador de dirección con features sintéticas (sin Spark ni MLflow)."""

from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from gasolina import modelo as M


def _features(n_semanas=40, semilla=0, ruido=0.0):
    """Serie sintética: la dirección siguiente es la contraria a la actual (según var_q_1)."""
    rng = np.random.default_rng(semilla)
    filas = []
    inicio = date(2025, 1, 7)  # martes
    for c in M.COMBUSTIBLES:
        var = rng.normal(0, 0.4, n_semanas + 1)
        for i in range(n_semanas):
            dir_act = "sube" if var[i] > 0.1 else "baja" if var[i] < -0.1 else "se_mantiene"
            señal = -var[i] + rng.normal(0, ruido)  # reversión: la base falla
            sig = "sube" if señal > 0.1 else "baja" if señal < -0.1 else "se_mantiene"
            filas.append({
                "semana_inicio": inicio + timedelta(days=7 * i), "combustible": c,
                "var_q_1": var[i], "var_q_2": var[i - 1] if i else None, "var_q_3": None,
                "var_q_4": None, "prom_movil_4": 30 + i * 0.01, "dif_super_diesel": 2.0,
                "direccion_actual": dir_act, "wti_var_1": None, "subsidio_activo": None,
                "direccion_siguiente": sig if i < n_semanas - 1 else None,
            })
    return pd.DataFrame(filas)


def test_division_temporal_no_mezcla_futuro():
    tr, te, ult = M.dividir_temporal(_features(), n_test=10)
    assert tr["semana_inicio"].max() < te["semana_inicio"].min()
    assert te["semana_inicio"].nunique() == 10
    assert len(ult) == 3 and ult["direccion_siguiente"].isna().all()


def test_muy_pocas_semanas():
    with pytest.raises(ValueError):
        M.dividir_temporal(_features(n_semanas=8), n_test=10)


def test_modelo_supera_linea_base_cuando_hay_senal():
    comp = M.entrenar_y_comparar(_features())
    assert set(comp.resultados) == {M.LINEA_BASE, "regresion_logistica", "arbol_decision"}
    assert comp.elegido != M.LINEA_BASE and comp.supera_baseline(comp.elegido)
    assert comp.n_prueba == 30


def test_sin_senal_puede_quedar_linea_base():
    df = _features()
    df["direccion_siguiente"] = df["direccion_actual"].shift(-3)  # la base acierta mucho
    df.loc[df.groupby("combustible").tail(1).index, "direccion_siguiente"] = None
    comp = M.entrenar_y_comparar(df)
    if comp.elegido == M.LINEA_BASE:
        assert not comp.supera_baseline(M.LINEA_BASE)
    else:
        assert comp.supera_baseline(comp.elegido)


def test_prediccion_y_metricas_cumplen_contrato():
    df = _features()
    comp = M.entrenar_y_comparar(df)
    mod = M.reentrenar_con_todo(df, comp.elegido)
    pred = M.predecir(df, comp.elegido, mod, "0.3.0", "run123")
    assert list(pred.columns) == M.COLUMNAS_PREDICCIONES and len(pred) == 3
    assert set(pred["prediccion"]) <= set(M.CLASES)
    assert pred["probabilidad"].between(0, 1).all()
    assert (pred["semana_objetivo"] == df["semana_inicio"].max() + timedelta(days=7)).all()
    met = M.filas_metricas(comp, "0.3.0", {"regresion_logistica": "r1"})
    assert list(met.columns) == M.COLUMNAS_METRICAS and met["es_champion"].sum() == 1


def test_prediccion_linea_base():
    df = _features()
    pred = M.predecir(df, M.LINEA_BASE, None, "0.3.0")
    assert (pred["prediccion"] == pred["prediccion_baseline"]).all()
    assert pred["probabilidad"].isna().all()


def test_unir_predicciones_llena_direccion_real():
    sem = date(2026, 11, 10)
    viejas = pd.DataFrame([{**dict.fromkeys(M.COLUMNAS_PREDICCIONES), "semana_objetivo": sem,
                            "combustible": "super", "prediccion": "sube"}])
    nuevas = pd.DataFrame([{**dict.fromkeys(M.COLUMNAS_PREDICCIONES),
                            "semana_objetivo": sem + timedelta(days=7), "combustible": "super",
                            "prediccion": "baja"}])
    var = pd.DataFrame([{"semana_inicio": sem, "combustible": "super", "direccion": "sube"}])
    todo = M.unir_predicciones(viejas, nuevas, var)
    assert len(todo) == 2
    assert todo.iloc[0]["direccion_real"] == "sube" and todo.iloc[1]["direccion_real"] is None
