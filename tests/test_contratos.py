"""Contratos de docs/instructivos/INSTRUCTIVO_GENERAL.md (sección 5). Si cambian, se cambian aquí.

- 5.2: salida de extraer_precios (Modelos).
- 5.4: columnas de las tablas Oro (las tablas de ejemplo deben respetarlas igual que las reales).
"""

from datetime import date

import pytest

CONTRATO_54 = {
    "precio_semanal": {"semana_inicio", "semana_fin", "combustible", "precio_promedio",
                       "precio_min", "precio_max", "n_registros", "fuente"},
    "variacion_semanal": {"semana_inicio", "combustible", "precio_promedio", "precio_anterior",
                          "dif_q", "dif_pct", "direccion", "umbral_q"},
    "features_modelo": {"semana_inicio", "combustible", "var_q_1", "var_q_2", "var_q_3",
                        "var_q_4", "prom_movil_4", "dif_super_diesel", "direccion_actual",
                        "wti_var_1", "subsidio_activo", "direccion_siguiente"},
    "predicciones": {"semana_objetivo", "combustible", "prediccion", "probabilidad",
                     "prediccion_baseline", "modelo", "version_modelo", "mlflow_run_id",
                     "fecha_generacion", "direccion_real"},
    "metricas_modelo": {"fecha_entrenamiento", "modelo", "version_modelo", "accuracy_modelo",
                        "accuracy_baseline", "f1_macro_modelo", "f1_macro_baseline",
                        "n_semanas_test", "supera_baseline", "mlflow_run_id", "es_champion"},
}


@pytest.mark.parametrize("tabla", sorted(CONTRATO_54))
def test_tablas_oro_demo(oro_demo, tabla):
    from deltalake import DeltaTable

    df = DeltaTable(str(oro_demo / tabla)).to_pandas()
    assert set(df.columns) == CONTRATO_54[tabla]
    assert len(df) > 0


def test_semanas_empiezan_en_martes(oro_demo):
    from deltalake import DeltaTable

    df = DeltaTable(str(oro_demo / "precio_semanal")).to_pandas()
    assert all(pd_fecha.weekday() == 1 for pd_fecha in df["semana_inicio"])  # 1 = martes
    assert set(df["combustible"]) == {"super", "regular", "diesel"}


def test_direcciones_validas(oro_demo):
    from deltalake import DeltaTable

    df = DeltaTable(str(oro_demo / "variacion_semanal")).to_pandas()
    assert set(df["direccion"].dropna()) <= {"sube", "baja", "se_mantiene"}


CONTRATO_52 = {"archivo", "modo", "metadata", "registros", "tipo_foto", "validaciones",
               "score_confianza", "motor", "preproc", "tiempo_ms", "version_modelo",
               "detecciones_crudas"}
METADATA_52 = {"archivo", "fecha_hora", "lat", "lon", "altitud", "modelo_camara", "ancho",
               "alto", "sha256"}
REGISTRO_52 = {"combustible", "precio_q_galon", "modalidad", "ubicacion", "confianza",
               "texto_fuente"}


def test_contrato_52_extraer_precios(tmp_path):
    from PIL import Image

    from gasolina.extraccion import extraer_precios

    ruta = tmp_path / "x.jpg"
    Image.new("RGB", (32, 32)).save(ruta)
    r = extraer_precios(ruta, fecha_carpeta=str(date(2026, 11, 10)))
    assert set(r) == CONTRATO_52
    assert set(r["metadata"]) == METADATA_52
    assert r["modo"] in ("stub", "real")
    assert r["tipo_foto"] in ("rotulo", "bomba", "tabla_mem", "desconocido")
    for reg in r["registros"]:
        assert set(reg) == REGISTRO_52
        assert reg["combustible"] in ("super", "regular", "diesel")
    for v in r["validaciones"]:
        assert set(v) == {"nombre", "estado", "mensaje"}
        assert v["estado"] in ("ok", "falla", "advertencia")
