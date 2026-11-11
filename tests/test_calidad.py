"""Pruebas de src/gasolina/calidad.py con casos sintéticos (pandas y, si hay pyspark, Spark)."""

from datetime import date

import pandas as pd
import pytest

from gasolina import calidad

HOY = date(2026, 11, 11)


def fila(**kw):
    base = {"fecha": date(2026, 11, 10), "combustible": "super", "precio_q_galon": 33.45,
            "modalidad": "autoservicio", "ubicacion": "Shell Km 14", "foto_origen": "s3://f/a.jpg",
            "confianza": 0.9, "motor": "rapidocr", "version_modelo": "0.2.0"}
    base.update(kw)
    return base


def aplicar(filas, **kw):
    return calidad.aplicar_reglas(pd.DataFrame(filas), hoy=HOY, **kw)


def test_fila_buena_pasa_sin_cambios():
    validos, rechazados = aplicar([fila()])
    assert len(validos) == 1 and rechazados.empty
    assert validos["precio_q_galon"].iloc[0] == 33.45
    assert "regla" not in validos.columns


@pytest.mark.parametrize(
    "precio,pasa", [(19.99, False), (20.0, True), (60.0, True), (60.01, False)])
def test_rango_precio_incluye_los_limites(precio, pasa):
    validos, rechazados = aplicar([fila(precio_q_galon=precio)])
    assert (len(validos) == 1) == pasa
    if not pasa:
        assert rechazados["regla"].iloc[0] == "rango_precio"
        assert "fuera de [20, 60]" in rechazados["motivo"].iloc[0]


def test_precio_ausente_incumple_rango():
    _, rechazados = aplicar([fila(precio_q_galon=None)])
    assert rechazados["regla"].iloc[0] == "rango_precio"
    assert rechazados["motivo"].iloc[0] == "precio ausente"


def test_combustible_fuera_del_catalogo_y_normalizacion():
    validos, rechazados = aplicar([fila(combustible="  DIESEL "), fila(combustible="vpower"),
                                   fila(combustible="gas")])
    assert validos["combustible"].tolist() == ["diesel"]
    assert set(rechazados["regla"]) == {"combustible_valido"}
    assert "'vpower' fuera del catálogo" in rechazados["motivo"].iloc[0]


def test_fecha_futura_hoy_y_ausente():
    validos, rechazados = aplicar([
        fila(fecha=HOY), fila(fecha=date(2026, 11, 12)), fila(fecha=None),
        fila(fecha="2026-11-09"), fila(fecha="no es fecha")])
    assert len(validos) == 2  # hoy y el texto ISO válido
    assert list(rechazados["regla"]) == ["fecha_no_futura"] * 3
    assert "posterior a hoy (2026-11-11)" in rechazados["motivo"].iloc[0]
    assert set(rechazados["motivo"].iloc[1:]) == {"fecha ausente o inválida"}


def test_confianza_minima_incluye_el_limite_y_nula_falla():
    validos, rechazados = aplicar([fila(confianza=0.5), fila(confianza=0.49), fila(confianza=None)])
    assert len(validos) == 1
    assert list(rechazados["regla"]) == ["confianza_minima"] * 2
    assert rechazados["motivo"].tolist() == ["confianza 0.49 < 0.5", "confianza ausente"]


def test_consistencia_super_mayor_que_regular_en_la_misma_foto():
    buena = [fila(combustible="super", precio_q_galon=33.0),
             fila(combustible="regular", precio_q_galon=31.0)]
    mala = [fila(foto_origen="s3://f/b.jpg", combustible="super", precio_q_galon=30.0),
            fila(foto_origen="s3://f/b.jpg", combustible="regular", precio_q_galon=30.0),
            fila(foto_origen="s3://f/b.jpg", combustible="diesel", precio_q_galon=28.0)]
    validos, rechazados = aplicar(buena + mala)
    assert len(validos) == 3  # las 2 de la foto buena + el diésel de la foto mala
    assert sorted(rechazados["combustible"]) == ["regular", "super"]
    assert set(rechazados["regla"]) == {"consistencia_gasolinas"}
    assert "super (30.00) no es mayor que regular (30.00)" in rechazados["motivo"].iloc[0]


def test_consistencia_no_mezcla_fotos_ni_modalidades():
    # super barato en una foto y regular caro en otra: no es incoherencia
    filas = [fila(foto_origen="s3://f/a.jpg", combustible="super", precio_q_galon=28.0),
             fila(foto_origen="s3://f/b.jpg", combustible="regular", precio_q_galon=29.0),
             # misma foto, modalidades distintas
             fila(foto_origen="s3://f/c.jpg", combustible="super", precio_q_galon=28.0,
                  modalidad="autoservicio"),
             fila(foto_origen="s3://f/c.jpg", combustible="regular", precio_q_galon=29.0,
                  modalidad="servicio_completo")]
    validos, rechazados = aplicar(filas)
    assert len(validos) == 4 and rechazados.empty


def test_foto_sin_precios_legibles_va_a_cuarentena_con_su_motivo():
    sin = fila(combustible=None, precio_q_galon=None, confianza=None, fecha=None)
    validos, rechazados = aplicar([sin])
    assert validos.empty
    assert rechazados["regla"].iloc[0] == "sin_precios_legibles"
    assert rechazados["motivo"].iloc[0] == "sin_precios_legibles"
    assert pd.isna(rechazados["combustible"].iloc[0])


def test_varias_reglas_una_fila_regla_de_mayor_prioridad_y_motivos_juntos():
    mala = fila(combustible="vpower", precio_q_galon=99.0, confianza=0.1)
    _, rechazados = aplicar([mala])
    assert len(rechazados) == 1
    assert rechazados["regla"].iloc[0] == "combustible_valido"
    motivo = rechazados["motivo"].iloc[0]
    assert motivo.count("; ") == 2
    assert "precio 99.00" in motivo and "confianza 0.10" in motivo


def test_modalidad_y_ubicacion_nulas_pasan_a_no_indica():
    validos, _ = aplicar([
        fila(modalidad=None, ubicacion=""),
        fila(modalidad="  ", ubicacion=None, combustible="regular", precio_q_galon=31.0)])
    assert validos["modalidad"].tolist() == ["no_indica"] * 2
    assert validos["ubicacion"].tolist() == ["no_indica"] * 2


def test_parametros_sustituyen_a_la_config():
    validos, rechazados = aplicar([fila(precio_q_galon=45.0)], rango=(20, 40))
    assert validos.empty and rechazados["regla"].iloc[0] == "rango_precio"
    validos, _ = aplicar([fila(confianza=0.3)], confianza_min=0.2)
    assert len(validos) == 1


def test_validos_mas_rechazados_es_la_entrada_y_resumen_por_regla():
    filas = [fila(), fila(precio_q_galon=5.0), fila(confianza=0.1), fila(precio_q_galon=70.0),
             fila(combustible=None, precio_q_galon=None)]
    validos, rechazados = aplicar(filas)
    assert len(validos) + len(rechazados) == len(filas)
    r = calidad.resumen_por_regla(rechazados)
    assert r["rango_precio"] == 2 and r["confianza_minima"] == 1 and r["sin_precios_legibles"] == 1
    assert r["fecha_no_futura"] == 0 and sum(r.values()) == len(rechazados)


def test_dataframe_vacio_no_truena():
    cols = list(fila().keys())
    validos, rechazados = calidad.aplicar_reglas(pd.DataFrame(columns=cols), hoy=HOY)
    assert validos.empty and rechazados.empty


# ------------------------------------------------------------------ Spark (si hay pyspark y Java)

@pytest.fixture(scope="module")
def spark():
    pytest.importorskip("pyspark")
    from pyspark.sql import SparkSession

    try:
        s = (SparkSession.builder.master("local[1]").appName("calidad-tests")
             .config("spark.ui.enabled", "false").config("spark.sql.shuffle.partitions", "1")
             .getOrCreate())
    except Exception as exc:  # sin Java
        pytest.skip(f"Spark no disponible: {exc}")
    yield s
    s.stop()


CASOS = [
    fila(),
    fila(precio_q_galon=19.99), fila(precio_q_galon=60.0), fila(precio_q_galon=None),
    fila(combustible="  DIESEL "), fila(combustible="vpower"), fila(combustible=None),
    fila(fecha=HOY), fila(fecha=date(2026, 11, 12)), fila(fecha=None),
    fila(confianza=0.5), fila(confianza=0.49), fila(confianza=None),
    fila(foto_origen="s3://f/b.jpg", combustible="super", precio_q_galon=30.0),
    fila(foto_origen="s3://f/b.jpg", combustible="regular", precio_q_galon=30.0),
    fila(foto_origen="s3://f/b.jpg", combustible="diesel", precio_q_galon=28.0),
    fila(foto_origen="s3://f/c.jpg", combustible="super", precio_q_galon=33.0),
    fila(foto_origen="s3://f/c.jpg", combustible="regular", precio_q_galon=31.0),
    fila(combustible="vpower", precio_q_galon=99.0, confianza=0.1),
    fila(combustible=None, precio_q_galon=None, confianza=None, fecha=None, foto_origen="s3://f/d.jpg"),
    fila(modalidad=None, ubicacion="", combustible="regular", precio_q_galon=31.0, foto_origen="s3://f/e.jpg"),
]


def test_spark_da_el_mismo_resultado_que_pandas(spark):
    from pyspark.sql.types import DateType, DoubleType, StringType, StructField, StructType

    esquema = StructType([
        StructField("fecha", DateType()), StructField("combustible", StringType()),
        StructField("precio_q_galon", DoubleType()), StructField("modalidad", StringType()),
        StructField("ubicacion", StringType()), StructField("foto_origen", StringType()),
        StructField("confianza", DoubleType()), StructField("motor", StringType()),
        StructField("version_modelo", StringType()),
    ])
    filas = [tuple(c[k.name] for k in esquema.fields) for c in CASOS]
    sdf = spark.createDataFrame(filas, esquema)

    v_s, r_s = calidad.aplicar_reglas_spark(sdf, hoy=HOY)
    v_p, r_p = calidad.aplicar_reglas(pd.DataFrame(CASOS), hoy=HOY)

    claves = ["foto_origen", "combustible", "precio_q_galon", "fecha", "confianza"]

    def canon(df, extra=()):
        df = df[[*claves, "modalidad", "ubicacion", *extra]].copy()
        df = df.astype(object).where(df.notna(), None)
        return sorted(map(str, df.itertuples(index=False, name=None)))

    assert canon(v_s.toPandas()) == canon(v_p)
    assert canon(r_s.toPandas(), ("regla", "motivo")) == canon(r_p, ("regla", "motivo"))
    assert v_s.count() + r_s.count() == len(CASOS)
