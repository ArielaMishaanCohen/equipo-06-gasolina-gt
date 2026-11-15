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
    assert todo.iloc[0]["direccion_real"] == "sube"
    assert todo.iloc[1]["direccion_real"] is None


def test_predice_la_ultima_semana_aunque_falte_direccion_actual():
    df = _features()
    ultima = df["semana_inicio"].max()
    df.loc[df["semana_inicio"] == ultima, ["direccion_actual", "var_q_1"]] = None  # hueco del MEM
    comp = M.entrenar_y_comparar(df)
    mod = M.reentrenar_con_todo(df, "regresion_logistica")
    pred = M.predecir(df, "regresion_logistica", mod, "0.3.0")
    assert len(pred) == 3
    assert (pred["semana_objetivo"] == ultima + timedelta(days=7)).all()
    assert set(pred["prediccion"]) <= set(M.CLASES) and pred["prediccion_baseline"].isna().all()
    assert comp.n_prueba == 30


def test_una_sola_clase_conserva_baseline_y_explica_logistica_omitida():
    df = _features()
    df["direccion_actual"] = "se_mantiene"
    df.loc[df["direccion_siguiente"].notna(), "direccion_siguiente"] = "se_mantiene"
    comp = M.entrenar_y_comparar(df)
    assert comp.elegido == M.LINEA_BASE
    assert comp.baseline.metricas["accuracy"] == 1
    assert "regresion_logistica" in comp.descartados
    assert "arbol_decision" in comp.resultados


def test_prediccion_baseline_no_necesita_historico_de_entrenamiento():
    df = _features(n_semanas=1)
    pred = M.predecir(df, M.LINEA_BASE, None, "test")
    assert len(pred) == 3


def test_baseline_omite_combustible_sin_direccion_en_lugar_de_publicar_clase_nula():
    df = _features(n_semanas=1)
    df.loc[df.combustible == "diesel", "direccion_actual"] = None
    pred = M.predecir(df, M.LINEA_BASE, None, "test")
    assert set(pred.combustible) == {"super", "regular"}
    assert pred.prediccion.notna().all()


@pytest.mark.parametrize("n_test", [0, -1, True, 1.5])
def test_rechaza_tamano_test_invalido(n_test):
    with pytest.raises(ValueError, match="entero positivo"):
        M.dividir_temporal(_features(), n_test)


@pytest.mark.parametrize("campo,valor", [
    ("direccion_siguiente", "estable"), ("combustible", "vpower"),
    ("semana_inicio", date(2025, 1, 8)),
])
def test_rechaza_datos_que_rompen_contrato(campo, valor):
    df = _features()
    df.loc[0, campo] = valor
    with pytest.raises(ValueError):
        M.entrenar_y_comparar(df)


def test_rechaza_llaves_duplicadas_antes_de_entrenar():
    df = _features()
    with pytest.raises(ValueError, match="duplicada"):
        M.entrenar_y_comparar(pd.concat([df, df.head(1)]))
