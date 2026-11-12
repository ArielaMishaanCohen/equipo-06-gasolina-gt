"""Pruebas de src/gasolina/features.py con series sintéticas (sin Spark ni red)."""

from datetime import date, timedelta

import pandas as pd
import pytest

from gasolina import features

MARTES = date(2026, 1, 6)  # martes


def semana(n: int) -> date:
    return MARTES + timedelta(days=7 * n)


def serie(valores: dict[int, float], comb="super") -> pd.DataFrame:
    """Serie semanal {n_semana: precio}; las semanas que no estén son huecos."""
    return pd.DataFrame([{"semana_inicio": semana(n), "combustible": comb, "precio_promedio": p}
                         for n, p in valores.items()])


def fila(df, n, comb="super"):
    r = df[(df["semana_inicio"] == semana(n)) & (df["combustible"] == comb)]
    assert len(r) == 1, f"semana {n}: {len(r)} filas"
    return r.iloc[0]


# ------------------------------------------------------------------------- dirección y variación

@pytest.mark.parametrize("dif,esperado", [
    (0.11, "sube"), (0.10, "se_mantiene"), (0.0, "se_mantiene"), (-0.10, "se_mantiene"),
    (-0.11, "baja"), (None, None), (float("nan"), None)])
def test_clasificar_direccion_respeta_el_umbral(dif, esperado):
    assert features.clasificar_direccion(dif, 0.10) == esperado


def test_umbral_no_se_rompe_por_decimales_binarios():
    # 30.20 - 30.10 = 0.0999999... o 0.1000000...1 en flotante: debe ser se_mantiene
    v = features.construir_variacion(serie({0: 30.10, 1: 30.20, 2: 30.10}))
    assert fila(v, 1)["direccion"] == "se_mantiene" and fila(v, 2)["direccion"] == "se_mantiene"


def test_variacion_basica():
    v = features.construir_variacion(serie({0: 30.00, 1: 30.50, 2: 30.20}), umbral_q=0.10)
    assert list(v.columns) == features.COLUMNAS_VARIACION
    assert pd.isna(fila(v, 0)["precio_anterior"]) and pd.isna(fila(v, 0)["dif_q"])
    assert fila(v, 0)["direccion"] is None
    r1, r2 = fila(v, 1), fila(v, 2)
    assert r1["precio_anterior"] == 30.00 and r1["dif_q"] == 0.50 and r1["dif_pct"] == 1.67
    assert r1["direccion"] == "sube" and r2["direccion"] == "baja" and r2["dif_q"] == -0.30
    assert set(v["umbral_q"]) == {0.10}


def test_variacion_contra_semana_ausente_es_nula_no_interpolada():
    # falta la semana 2: la semana 3 NO se compara con la 1
    v = features.construir_variacion(serie({0: 30.0, 1: 31.0, 3: 35.0, 4: 35.5}))
    assert fila(v, 1)["dif_q"] == 1.0
    assert pd.isna(fila(v, 3)["dif_q"]) and pd.isna(fila(v, 3)["precio_anterior"])
    assert fila(v, 3)["direccion"] is None
    assert fila(v, 4)["dif_q"] == 0.5 and fila(v, 4)["direccion"] == "sube"
    assert len(v) == 4  # no se agregan filas para las semanas faltantes


def test_variacion_por_combustible_independiente():
    df = pd.concat([serie({0: 30.0, 1: 31.0}, "super"), serie({0: 28.0, 2: 27.0}, "regular")])
    v = features.construir_variacion(df)
    assert fila(v, 1, "super")["dif_q"] == 1.0
    assert pd.isna(fila(v, 2, "regular")["dif_q"])


def test_variacion_rechaza_duplicados_y_dias_que_no_son_martes():
    with pytest.raises(ValueError, match="más de una fila"):
        features.construir_variacion(pd.concat([serie({0: 30.0}), serie({0: 31.0})]))
    lunes = pd.DataFrame([{"semana_inicio": date(2026, 1, 5), "combustible": "super",
                           "precio_promedio": 30.0}])
    with pytest.raises(ValueError, match="martes"):
        features.construir_variacion(lunes)


def test_entradas_vacias_devuelven_tablas_vacias_con_columnas():
    v = features.construir_variacion(pd.DataFrame())
    assert v.empty and list(v.columns) == features.COLUMNAS_VARIACION
    f = features.construir_features(v)
    assert f.empty and list(f.columns) == features.COLUMNAS_FEATURES


# ---------------------------------------------------------------------------------- features

def test_features_sin_huecos():
    precios = {0: 30.0, 1: 30.5, 2: 30.3, 3: 30.3, 4: 31.0, 5: 31.1}
    v = features.construir_variacion(serie(precios))
    f = features.construir_features(v)
    assert list(f.columns) == features.COLUMNAS_FEATURES and len(f) == 6
    r = fila(f, 4)
    assert (r["var_q_1"], r["var_q_2"], r["var_q_3"], r["var_q_4"]) == (0.7, 0.0, -0.2, 0.5)
    assert r["prom_movil_4"] == round((30.5 + 30.3 + 30.3 + 31.0) / 4, 2)
    assert r["direccion_actual"] == "sube" and r["direccion_siguiente"] == "se_mantiene"
    # la primera semana no tiene variación; var_q_k necesita k semanas de historia
    assert pd.isna(fila(f, 0)["var_q_1"]) and pd.isna(fila(f, 1)["var_q_2"])
    # última semana: sin objetivo
    assert fila(f, 5)["direccion_siguiente"] is None


def test_hueco_deja_nulos_var_q_y_prom_movil_en_las_semanas_siguientes():
    # falta la semana 5: afecta a las semanas 6 a 9
    precios = {n: 30.0 + 0.5 * n for n in range(0, 12) if n != 5}
    f = features.construir_features(features.construir_variacion(serie(precios)))
    assert len(f) == 11
    r6 = fila(f, 6)
    assert pd.isna(r6["var_q_1"])  # su semana anterior no existe
    assert pd.isna(r6["prom_movil_4"])
    r7 = fila(f, 7)
    assert r7["var_q_1"] == 0.5 and pd.isna(r7["var_q_2"])  # var_q_2 usa la variación de la sem. 6
    assert pd.isna(r7["prom_movil_4"])
    r8, r9 = fila(f, 8), fila(f, 9)
    assert pd.isna(r8["var_q_3"]) and pd.isna(r9["var_q_4"]) and pd.isna(r8["prom_movil_4"])
    r10 = fila(f, 10)
    assert r10["var_q_4"] == 0.5
    assert r10["prom_movil_4"] == round((33.5 + 34.0 + 34.5 + 35.0) / 4, 2)
    # antes del hueco todo sigue completo
    assert fila(f, 4)["var_q_4"] == 0.5 and fila(f, 4)["prom_movil_4"] is not None


def test_direccion_siguiente_nula_si_falta_la_semana_siguiente():
    f = features.construir_features(features.construir_variacion(
        serie({0: 30.0, 1: 31.0, 2: 32.0, 4: 33.0, 5: 34.0})))
    assert fila(f, 1)["direccion_siguiente"] == "sube"
    assert fila(f, 2)["direccion_siguiente"] is None   # la semana 3 no existe
    assert fila(f, 4)["direccion_actual"] is None       # su semana anterior no existe
    assert fila(f, 4)["direccion_siguiente"] == "sube"  # la 5 sí existe y sube
    assert fila(f, 5)["direccion_siguiente"] is None


def test_dif_super_diesel_misma_semana_y_nula_si_falta_alguno():
    df = pd.concat([serie({0: 33.0, 1: 34.0, 2: 35.0}, "super"),
                    serie({0: 30.0, 2: 31.0}, "diesel"),
                    serie({0: 32.0, 1: 33.0, 2: 34.0}, "regular")])
    f = features.construir_features(features.construir_variacion(df))
    assert fila(f, 0, "regular")["dif_super_diesel"] == 3.0  # aparece en las filas de todos
    assert fila(f, 2, "super")["dif_super_diesel"] == 4.0
    assert pd.isna(fila(f, 1, "super")["dif_super_diesel"])  # no hay diésel esa semana


def test_wti_var_1_usa_semana_anterior_y_deja_huecos_nulos():
    v = features.construir_variacion(serie({n: 30.0 + n for n in range(5)}))
    wti = pd.DataFrame({"semana_inicio": [semana(0), semana(1), semana(3), semana(4)],
                        "wti_promedio": [60.0, 62.5, 61.0, 59.0]})
    f = features.construir_features(v, wti_semanal=wti)
    assert pd.isna(fila(f, 0)["wti_var_1"])
    assert fila(f, 1)["wti_var_1"] == 2.5
    assert pd.isna(fila(f, 2)["wti_var_1"]) and pd.isna(fila(f, 3)["wti_var_1"])  # sem. 2 sin WTI
    assert fila(f, 4)["wti_var_1"] == -2.0


def test_sin_wti_ni_eventos_las_columnas_opcionales_son_nulas():
    f = features.construir_features(features.construir_variacion(serie({0: 30.0, 1: 31.0})))
    assert f["wti_var_1"].isna().all() and f["subsidio_activo"].isna().all()


# ------------------------------------------------------------------------------------ subsidio

EVENTOS = pd.DataFrame([
    # inicio confirmado, fin SIN confirmar (campo vacío)
    {"fecha_inicio": "2026-04-28", "fecha_fin": ""},
    # inicio sin confirmar, fin confirmado
    {"fecha_inicio": "", "fecha_fin": "2026-12-31"},
    # inicio y fin confirmados
    {"fecha_inicio": "2026-10-01", "fecha_fin": "2026-12-31"},
])


def sub(eventos, *fechas):
    s = features.subsidio_activo_semanas([date.fromisoformat(f) for f in fechas], eventos)
    return [None if pd.isna(x) else int(x) for x in s]


def test_subsidio_antes_del_primer_inicio_confirmado_es_cero():
    assert sub(EVENTOS, "2025-06-03", "2026-04-14") == [0, 0]  # la sem. del 14/04 termina el 20/04


def test_subsidio_semana_del_inicio_confirmado_es_uno_y_despues_es_nulo():
    # 28/04/2026 es martes: esa semana tiene el inicio; luego el fin no está confirmado
    assert sub(EVENTOS, "2026-04-28") == [1]
    assert sub(EVENTOS, "2026-05-05", "2026-07-07", "2026-09-22") == [None, None, None]


def test_subsidio_con_fechas_completas_es_uno_y_la_semana_del_inicio_cuenta():
    # 01/10/2026 es jueves: la semana del 29/09 al 05/10 lo contiene
    assert sub(EVENTOS, "2026-09-29", "2026-10-06", "2026-12-29") == [1, 1, 1]


def test_subsidio_sin_ninguna_fecha_confirmada_es_nulo():
    vacios = pd.DataFrame([{"fecha_inicio": "", "fecha_fin": ""}])
    assert sub(vacios, "2026-05-05") == [None]
    assert sub(None, "2026-05-05") == [None]
    assert sub(pd.DataFrame(columns=["fecha_inicio", "fecha_fin"]), "2026-05-05") == [None]


def test_subsidio_evento_completo_no_inventa_fechas_fuera_de_su_rango():
    solo = pd.DataFrame([{"fecha_inicio": "2026-04-28", "fecha_fin": "2026-07-02"}])
    assert sub(solo, "2026-04-21", "2026-04-28", "2026-06-30", "2026-07-07") == [0, 1, 1, 0]


def test_subsidio_acepta_nan_y_fechas_tipo_date():
    ev = pd.DataFrame({"fecha_inicio": [date(2026, 4, 28)], "fecha_fin": [float("nan")]})
    assert sub(ev, "2026-04-28", "2026-05-12") == [1, None]


def test_features_integran_subsidio_como_entero_con_nulos():
    precios = {0: 30.0, 1: 30.1}
    ev = pd.DataFrame([{"fecha_inicio": "2026-01-13", "fecha_fin": ""}])  # semana 1 (martes 13/01)
    f = features.construir_features(features.construir_variacion(serie(precios)),
                                    eventos_subsidio=ev)
    assert fila(f, 0)["subsidio_activo"] == 0 and fila(f, 1)["subsidio_activo"] == 1
