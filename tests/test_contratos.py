"""Los artifacts demo y la salida de extraer_precios respetan EXACTAMENTE los contratos
de docs/INSTRUCTIVO_GENERAL.md (sección 4). Si un contrato cambia, se cambia aquí también."""

import json

import pytest
from conftest import RAIZ

DEMO = RAIZ / "artifacts_demo"
COMB4 = {"diesel", "regular", "super", "vpower"}
COMB3 = {"diesel", "regular", "super"}

# Contrato 4.2: claves de primer nivel
CONTRATO_42 = {
    "ocr_config.json": {
        "origen", "fecha", "version", "motor", "preproc", "segunda_pasada", "estrategia",
        "umbral_score", "metricas", "mlflow_run_id",
    },
    "forecast_meta.json": {
        "origen", "fecha", "modelo", "version", "features", "metricas_validacion",
        "fecha_entrenamiento",
    },
    "predicciones.json": {
        "origen", "fecha", "semana_objetivo", "modelo", "version", "predicciones",
    },
    "reglas.json": {"origen", "fecha", "rango_precio", "referencia_mem", "diferencias"},
    "historico.json": {"origen", "fecha", "mem", "fotos"},
    "monitoreo.json": {
        "origen", "fecha", "version_champion", "fecha_reentrenamiento", "error_produccion",
        "error_validacion", "drift_vs_mem_pct", "alertas",
    },
}


def _cargar(nombre):
    return json.loads((DEMO / nombre).read_text(encoding="utf-8"))


@pytest.mark.parametrize("nombre", sorted(CONTRATO_42))
def test_claves_primer_nivel_y_origen_demo(nombre):
    d = _cargar(nombre)
    assert set(d) == CONTRATO_42[nombre]
    assert d["origen"] == "demo"
    assert isinstance(d["fecha"], str) and d["fecha"][:4].isdigit()


def test_ocr_config_anidado():
    d = _cargar("ocr_config.json")
    assert set(d["metricas"]) == {
        "accuracy_precio", "mae", "pct_fotos_4_correctos", "tiempo_ms_promedio",
    }


def test_forecast_meta_anidado():
    d = _cargar("forecast_meta.json")
    assert isinstance(d["features"], list)
    assert set(d["metricas_validacion"]) == {"mae", "rmse", "mape", "mejora_vs_baseline_pct"}


def test_predicciones_anidado():
    d = _cargar("predicciones.json")
    assert d["predicciones"]
    for p in d["predicciones"]:
        assert set(p) == {"combustible", "prediccion", "intervalo_inf", "intervalo_sup"}
        assert p["combustible"] in COMB4


def test_reglas_anidado():
    d = _cargar("reglas.json")
    assert set(d["rango_precio"]) == COMB4
    assert all(len(v) == 2 for v in d["rango_precio"].values())
    assert set(d["referencia_mem"]) == {"fecha_referencia"} | COMB3
    assert set(d["diferencias"]) == {"super_menos_regular", "vpower_menos_super", "tolerancia"}


def test_historico_anidado():
    d = _cargar("historico.json")
    for m in d["mem"]:
        assert set(m) == {"semana", "fecha", "combustible", "precio"}
    for f in d["fotos"]:
        assert set(f) == {"fecha", "combustible", "precio", "estacion_id", "score_confianza"}


def test_monitoreo_anidado():
    d = _cargar("monitoreo.json")
    assert set(d["error_produccion"]) == {"mae"}
    assert set(d["error_validacion"]) == {"mae"}
    assert set(d["drift_vs_mem_pct"]) == COMB3
    for a in d["alertas"]:
        assert set(a) == {"nombre", "activa", "valor", "umbral", "mensaje"}


# Contrato 4.1: salida de extraer_precios
CONTRATO_41 = {
    "archivo", "modo", "metadata", "ruta_a", "precios", "fuentes", "combustible_despachado",
    "validaciones", "score_confianza", "estrategia", "motor", "preproc", "segunda_pasada",
    "tiempo_ms", "version_modelo", "detecciones_crudas",
}
METADATA_41 = {
    "archivo", "fecha_hora", "lat", "lon", "altitud", "modelo_camara", "ancho", "alto", "sha256",
}
FUENTES_41 = {"ruta_A", "ruta_B", "ambas", "corregido_por_ruta_A", "inferido", None}


def test_contrato_41_extraer_precios(tmp_path):
    from PIL import Image

    from gasolina.extraccion import extraer_precios

    ruta = tmp_path / "x.jpg"
    Image.new("RGB", (32, 32)).save(ruta)
    r = extraer_precios(ruta)
    assert set(r) == CONTRATO_41
    assert set(r["metadata"]) == METADATA_41
    assert set(r["ruta_a"]) == {"total", "galones", "precio_a"}
    assert set(r["precios"]) == COMB4
    assert set(r["fuentes"]) == COMB4
    assert set(r["fuentes"].values()) <= FUENTES_41
    assert r["modo"] in ("stub", "real")
    for v in r["validaciones"]:
        assert set(v) == {"nombre", "estado", "mensaje"}
        assert v["estado"] in ("ok", "falla", "advertencia")
