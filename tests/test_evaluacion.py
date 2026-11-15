"""Evita aciertos inflados por etiquetas ambiguas y selección con fotos ausentes."""

import json

import pytest

from gasolina.evaluacion import cargar_etiquetas, comparar, elegir_configuracion, evaluar_carpeta


def test_csv_bom_ruta_windows_y_duplicados(tmp_path):
    ruta = tmp_path / "etiquetas.csv"
    ruta.write_text("foto,combustible,precio_q_galon\n"
                    "carpeta\\a.jpg,super,33.45\n", encoding="utf-8-sig")
    assert cargar_etiquetas(ruta)["a.jpg"]["super"]["precio"] == 33.45
    with ruta.open("a", encoding="utf-8") as archivo:
        archivo.write("a.jpg,super,32.45\n")
    with pytest.raises(ValueError, match="duplicada"):
        cargar_etiquetas(ruta)


def test_distingue_faltantes_duplicados_y_salidas_sin_verdad_manual():
    etiquetas = {"a.jpg": {"super": {"precio": 33.45, "lectura": "a_simple_vista"},
                           "regular": {"precio": 32.45, "lectura": "a_simple_vista"}}}
    resultados = {"a.jpg": {"registros": [
        {"combustible": "super", "precio_q_galon": 31.00},
        {"combustible": "super", "precio_q_galon": 33.45},
        {"combustible": "diesel", "precio_q_galon": 25.00},
    ]}}
    metricas = comparar(resultados, etiquetas)["metricas"]
    assert metricas["correctos"] == 1
    assert metricas["falsos_positivos"] == 1
    assert metricas["no_encontrados"] == 1
    assert metricas["sin_etiqueta"] == 1
    assert metricas["pct_fotos_completas"] == 0


def test_tolerancia_estricta_de_medio_centavo():
    verdad = {"a.jpg": {"super": {"precio": 33.45, "lectura": "a_simple_vista"}}}
    salida = {"a.jpg": {"registros": [{"combustible": "super", "precio_q_galon": 33.455}]}}
    assert comparar(salida, verdad)["metricas"]["incorrectos"] == 1


def test_no_sobrescribe_fotos_con_mismo_nombre_en_subcarpetas(tmp_path):
    etiquetas = tmp_path / "etiquetas.csv"
    etiquetas.write_text("foto,combustible,precio_q_galon\na.jpg,super,33.45\n", encoding="utf-8")
    for carpeta in ("semana1", "semana2"):
        (tmp_path / carpeta).mkdir()
        (tmp_path / carpeta / "a.jpg").write_bytes(b"foto")
    with pytest.raises(ValueError, match="ambiguo"):
        evaluar_carpeta(etiquetas, tmp_path)


def corrida(exactitud=90, tiempo=100, n=20, ausentes=0):
    return {"metricas": {"pct_precios_correctos": exactitud, "pct_fotos_completas": 80,
                         "falsos_positivos": 0, "tiempo_ms_promedio": tiempo,
                         "fotos_ausentes": ausentes},
            "por_foto": [{"foto": str(i)} for i in range(n)],
            "parametros": {"motor": "rapidocr", "preproc": "ninguno"}}


def test_seleccion_ocr_prioriza_exactitud_y_desempata_por_latencia():
    lenta, rapida, peor = corrida(tiempo=200), corrida(), corrida(80, tiempo=1)
    assert elegir_configuracion([lenta, peor, rapida]) is rapida


@pytest.mark.parametrize("corridas", [[], [corrida(n=5)], [corrida(ausentes=1)],
                                      [corrida(), corrida(n=21)]])
def test_seleccion_ocr_rechaza_evidencia_incompleta(corridas):
    with pytest.raises(ValueError):
        elegir_configuracion(corridas)


def test_cli_guarda_detalle_aunque_consola_solo_muestre_resumen(tmp_path, monkeypatch, capsys):
    from gasolina.cli import evaluar

    etiquetas = tmp_path / "etiquetas.csv"
    etiquetas.touch()
    salida = tmp_path / "resultado.json"
    monkeypatch.setattr("gasolina.evaluacion.evaluar_carpeta", lambda *a, **kw: corrida())
    evaluar(["--etiquetas", str(etiquetas), "--comparar-preprocs", "--salida", str(salida)])
    guardado = json.loads(salida.read_text(encoding="utf-8"))
    consola = json.loads(capsys.readouterr().out)
    assert len(guardado["corridas"]) == 4
    assert "por_foto" in guardado["corridas"][0]
    assert "por_foto" not in consola["corridas"][0]
