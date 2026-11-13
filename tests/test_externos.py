"""Pruebas de src/gasolina/externos.py con texto sintético (sin PDFs ni red)."""

from datetime import date

import pandas as pd
import pytest

from gasolina import externos

# Formato 2026: etiqueta y 7 valores en la misma línea, con "Q".
TEXTO_2026 = """
INFORME EJECUTIVO DE PRECIOS DE LOS COMBUSTIBLES
Producto 5/10/2026 12/10/2026 Diferencia
Gasolina Superior Q36.19 Q36.17 -Q0.02
Producto 31/08/2026 07/09/2026 16/09/2026 24/09/2026 28/09/2026 05/10/2026 12/10/2026
Gasolina Superior Q43.06 Q44.66 Q44.66 Q44.61 Q44.61 Q36.18 Q36.17
Gasolina Regular Q40.93 Q42.58 Q42.58 Q42.58 Q42.58 Q34.85 Q34.86
Combustible Diesel Q46.37 Q49.36 Q49.36 Q49.40 Q49.40 Q41.72 Q41.69
Precios promedio semanales
"""

# Formato 2025-10: sin "Q" y con etiquetas cortas.
TEXTO_SIN_Q = """
Producto 25/08/2025 01/09/2025 08/09/2025 16/09/2025 22/09/2025 29/09/2025 06/10/2025
Superior 30.04 30.04 30.06 29.97 29.94 29.95 29.96
Regular 28.54 28.56 28.56 28.48 28.45 28.45 28.46
Diesel 26.06 26.01 26.02 25.99 26.39 26.38 26.38
Fuente: Departamento de Análisis Económico
"""

# Formato 2025-03: etiqueta sola y valores en la línea siguiente; fechas sin "Producto".
TEXTO_ETIQUETA_SOLA = """
Unidad: Q/galón
27/01/2025 03/02/2025 10/02/2025 17/02/2025 24/02/2025 03/03/2025 10/03/2025
Producto
Superior
30.61 30.67 30.17 30.69 30.76 30.76 29.88
Regular
29.11 29.18 28.66 29.18 29.26 29.26 28.39
Diesel
27.73 27.79 27.02 27.58 27.67 27.67 26.81
Fuente: Departamento de Análisis Económico, DGH, MEM
"""


def _precio(df, fecha, comb):
    fila = df[(df["fecha"] == fecha) & (df["combustible"] == comb)]
    assert len(fila) == 1
    return fila["precio_promedio"].iloc[0]


def test_parsea_formato_2026_ignora_comparacion_de_dos_fechas():
    df = externos.parsear_texto_mem(TEXTO_2026, "a.pdf")
    assert len(df) == 21  # 3 combustibles x 7 fechas; la tabla de 2 fechas no cuenta
    assert _precio(df, date(2026, 9, 7), "super") == 44.66
    assert _precio(df, date(2026, 10, 12), "diesel") == 41.69
    assert set(df["modalidad"]) == {"autoservicio"}


def test_parsea_formato_sin_q_y_etiquetas_cortas():
    df = externos.parsear_texto_mem(TEXTO_SIN_Q, "b.pdf")
    assert len(df) == 21
    assert _precio(df, date(2025, 8, 25), "regular") == 28.54


def test_parsea_formato_etiqueta_sola():
    df = externos.parsear_texto_mem(TEXTO_ETIQUETA_SOLA, "c.pdf")
    assert len(df) == 21
    assert _precio(df, date(2025, 2, 3), "super") == 30.67
    assert _precio(df, date(2025, 3, 10), "diesel") == 26.81


def test_texto_sin_tabla_devuelve_vacio_con_columnas():
    df = externos.parsear_texto_mem("nada que ver\n12/10/2026 Q1.00", "x.pdf")
    assert df.empty and list(df.columns) == externos.COLUMNAS_MEM


@pytest.mark.parametrize("fecha,esperado", [
    (date(2026, 11, 10), date(2026, 11, 10)),  # martes
    (date(2026, 11, 16), date(2026, 11, 10)),  # lunes: cierra la semana del martes anterior
    (date(2026, 11, 17), date(2026, 11, 17)),  # martes siguiente
    (date(2026, 11, 15), date(2026, 11, 10)),  # domingo
    (date(2025, 1, 6), date(2024, 12, 31)),    # lunes que cruza el año
])
def test_semana_inicio_martes_a_lunes(fecha, esperado):
    r = externos.semana_inicio(fecha)
    assert r == esperado and r.weekday() == 1


def test_consolidar_gana_informe_mas_reciente():
    viejo = externos.parsear_texto_mem(TEXTO_SIN_Q, "viejo.pdf")
    nuevo = viejo.copy()
    nuevo["fuente_pdf"] = "nuevo.pdf"
    nuevo["fecha"] = nuevo["fecha"] + pd.Timedelta(days=7)  # informe posterior, solapa 6 fechas
    es_celda = (nuevo["fecha"] == date(2025, 9, 8)) & (nuevo["combustible"] == "super")
    nuevo.loc[es_celda, "precio_promedio"] = 99.0
    out = externos.consolidar_mem([viejo, nuevo])
    assert not out.duplicated(["fecha", "combustible", "modalidad"]).any()
    assert _precio(out, date(2025, 9, 8), "super") == 99.0


def test_conflictos_detecta_precios_distintos_en_la_misma_fecha():
    a = externos.parsear_texto_mem(TEXTO_SIN_Q, "a.pdf")
    b = a.copy()
    b["fuente_pdf"] = "b.pdf"
    es_celda = (b["fecha"] == date(2025, 9, 1)) & (b["combustible"] == "diesel")
    b.loc[es_celda, "precio_promedio"] = 30.0
    c = externos.conflictos_mem([a, b])
    assert len(c) == 2 and set(c["fecha"]) == {date(2025, 9, 1)}


def test_a_semanal_promedia_monitoreos_de_la_misma_semana_y_no_inventa():
    # 09/04/2026 (jueves) y 13/04/2026 (lunes) caen en la misma semana martes-lunes (07/04).
    df = pd.DataFrame({
        "fecha": [date(2026, 4, 9), date(2026, 4, 13), date(2026, 4, 16)],
        "combustible": ["super"] * 3,
        "precio_promedio": [40.48, 39.98, 39.19],
        "modalidad": ["autoservicio"] * 3,
        "fuente_pdf": ["x.pdf"] * 3,
    })
    sem = externos.a_semanal(df, fuente_urls={"x.pdf": "https://ejemplo/x.pdf"})
    assert list(sem.columns) == externos.COLUMNAS_MEM_REFERENCIA
    assert list(sem["semana_inicio"]) == [date(2026, 4, 7), date(2026, 4, 14)]
    assert sem["precio_q_galon"].tolist() == [40.23, 39.19]
    assert set(sem["fuente_url"]) == {"https://ejemplo/x.pdf"}
    assert set(sem["region"]) == {"Ciudad de Guatemala"}


def test_semanas_faltantes_lista_los_huecos():
    sem = pd.DataFrame({"semana_inicio": [date(2026, 11, 3), date(2026, 11, 10)],
                        "combustible": ["super", "super"]})
    f = externos.semanas_faltantes(sem, date(2026, 11, 3), date(2026, 11, 16))
    assert (date(2026, 11, 3), "super") not in set(zip(f["semana_inicio"], f["combustible"]))
    assert len(f) == 4  # 2 semanas x 3 combustibles = 6; super ya tiene las 2
    assert set(f["combustible"]) == {"regular", "diesel"}


def test_leer_fred_convierte_punto_a_nan(tmp_path):
    csv = tmp_path / "wti.csv"
    csv.write_text("observation_date,DCOILWTICO\n2026-11-02,61.2\n2026-11-03,.\n2026-11-04,\n")
    df = externos.leer_fred(csv)
    assert list(df.columns) == ["fecha", "serie", "valor"]
    assert df["serie"].iloc[0] == "DCOILWTICO"
    assert df["valor"].iloc[0] == 61.2 and df["valor"].iloc[1:].isna().all()


def test_ignora_tabla_con_fechas_desordenadas():
    # Comparación entre países de un informe real: no es una serie cronológica.
    texto = ("Fecha de Monitoreo 2/07/2025 28/06/2025 30/06/2025 28/06/2025 2/07/2025 30/06/2025\n"
             "Gasolina Superior Q30.96 Q29.95 Q30.41 Q38.86 Q38.09 Q26.97\n")
    assert externos.parsear_texto_mem(texto, "ca.pdf").empty


def test_consolidar_con_conflictos_gana_mayoria_clara_o_queda_hueco():
    base = externos.parsear_texto_mem(TEXTO_SIN_Q, "a.pdf")

    def copia(nombre, cambios):
        d = base.copy()
        d["fuente_pdf"] = nombre
        for (f, c), v in cambios.items():
            d.loc[(d["fecha"] == f) & (d["combustible"] == c), "precio_promedio"] = v
        return d

    dif = date(2025, 9, 1)
    # diesel 01/09: 3 informes dicen 26.01 y uno dice 30.0 -> gana 26.01 (3 >= 2*1)
    # regular 01/09: 2 dicen 28.56 y 2 dicen 29.0 -> empate -> hueco
    dfs = [base,
           copia("b.pdf", {(dif, "diesel"): 30.0, (dif, "regular"): 29.0}),
           copia("c.pdf", {(dif, "regular"): 29.0}),
           copia("d.pdf", {})]
    out = externos.consolidar_mem(dfs, excluir_conflictos=True)
    fila = out[(out["fecha"] == dif) & (out["combustible"] == "diesel")]
    assert fila["precio_promedio"].iloc[0] == 26.01
    assert out[(out["fecha"] == dif) & (out["combustible"] == "regular")].empty
    # redondeo de 0.01 no cuenta como conflicto y no pierde la fila
    dfs2 = [base, copia("e.pdf", {(date(2025, 9, 8), "super"): 30.07})]
    out2 = externos.consolidar_mem(dfs2, excluir_conflictos=True)
    assert len(out2[(out2["fecha"] == date(2025, 9, 8)) & (out2["combustible"] == "super")]) == 1
    # sin excluir: gana el informe más reciente (aquí no hay conflicto de fechas: 21 filas)
    assert len(externos.consolidar_mem(dfs)) == 21
