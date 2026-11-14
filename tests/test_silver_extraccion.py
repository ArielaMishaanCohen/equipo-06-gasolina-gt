"""Integración bytes -> lotes de Spark -> contrato de Plata y evaluación manual."""

import json
from datetime import date

import pandas as pd
import pytest

from gasolina import __version__, extraccion
from gasolina.calidad import aplicar_reglas
from gasolina.silver_extraccion import candidatos_lote, evaluar_resultados, extraer_lote


def resultado(registros, fecha="2026-01-07T08:30:00"):
    return {"metadata": {"fecha_hora": fecha}, "registros": registros,
            "motor": "rapidocr", "version_modelo": __version__,
            "score_confianza": 0.9, "tiempo_ms": 10}


def registro(combustible="super", precio=33.45):
    return {"combustible": combustible, "precio_q_galon": precio,
            "modalidad": None, "ubicacion": "  ", "confianza": 0.95}


def test_bytes_fecha_carpeta_y_explosion_sin_releer_ocr(monkeypatch):
    llamadas = []

    def extraer(contenido, **kwargs):
        llamadas.append((contenido, kwargs))
        return resultado([registro(), registro("regular", 32.45)])

    monkeypatch.setattr(extraccion, "extraer_precios", extraer)
    lote = pd.DataFrame([
        {"path": "s3://raw/2026-01-07/a.HEIC", "content": bytearray(b"imagen"),
         "fecha_carpeta": date(2026, 1, 7)},
        {"path": "s3://raw/b.HEIC", "content": b"otra", "fecha_carpeta": pd.NaT},
    ])
    salidas = list(extraer_lote(iter([lote]), version_modelo=__version__))
    candidatos = pd.concat(candidatos_lote(iter(salidas)), ignore_index=True)
    assert len(llamadas) == 2  # explotar no ejecuta OCR otra vez
    assert llamadas[0] == (b"imagen", {"nombre": "a.HEIC", "fecha_carpeta": "2026-01-07",
                                      "motor": "rapidocr", "preproc": "gris_clahe"})
    assert llamadas[1][1]["fecha_carpeta"] is None
    assert len(candidatos) == 4
    assert set(candidatos.fecha) == {date(2026, 1, 7)}
    assert set(candidatos.modalidad) == {"no_indica"}
    assert set(candidatos.ubicacion) == {"no_indica"}
    validos, rechazados = aplicar_reglas(candidatos, hoy=date(2026, 11, 13))
    assert len(validos) == 4 and rechazados.empty


def test_sin_precios_llega_a_cuarentena_con_ruta_completa():
    datos = pd.DataFrame([{"foto_origen": "s3://raw/sin_precios.HEIC",
                           "resultado_json": json.dumps(resultado([]))}])
    candidatos = pd.concat(candidatos_lote(iter([datos])), ignore_index=True)
    validos, rechazados = aplicar_reglas(candidatos)
    assert validos.empty
    assert len(rechazados) == 1
    assert rechazados.iloc[0].motivo == "sin_precios_legibles"
    assert rechazados.iloc[0].foto_origen == "s3://raw/sin_precios.HEIC"


def test_error_infraestructura_no_se_disfraza_de_foto_sin_precios(monkeypatch):
    def falla(*args, **kwargs):
        raise ImportError("onnxruntime no instalado")

    monkeypatch.setattr(extraccion, "extraer_precios", falla)
    lote = pd.DataFrame([{"path": "s3://raw/a.HEIC", "content": b"foto", "fecha_carpeta": None}])
    with pytest.raises(ImportError, match="onnxruntime"):
        list(extraer_lote(iter([lote])))
    with pytest.raises(RuntimeError, match="Versión distinta"):
        list(extraer_lote(iter([lote]), version_modelo="otra"))


def test_evaluacion_cuenta_fotos_ausentes_y_lecturas_sin_etiqueta():
    etiquetas = [
        {"foto": "a.HEIC", "combustible": "super", "precio_q_galon": "33.45"},
        {"foto": "a.HEIC", "combustible": "regular", "precio_q_galon": "32.45"},
        {"foto": "ausente.HEIC", "combustible": "super", "precio_q_galon": "34.45"},
    ]
    fotos = [{"foto_origen": "s3://raw/a.HEIC", "resultado_json": json.dumps(
        resultado([registro(), registro("regular", 32.46), registro("diesel", 25.00)]))}]
    resumen, detalle = evaluar_resultados(fotos, etiquetas)
    assert resumen["correctos"] == 1
    assert resumen["incorrectos"] == 1
    assert resumen["no_encontrados"] == 1
    assert resumen["sin_etiqueta"] == 1
    assert resumen["pct_precios_correctos"] == 33.3
    assert resumen["fotos_ausentes"] == 1
    assert len(detalle) == 2
    assert detalle[1]["foto_en_bronce"] is False
    with pytest.raises(ValueError, match="ambiguo"):
        evaluar_resultados(fotos * 2, etiquetas)
    with pytest.raises(ValueError, match="duplicada"):
        evaluar_resultados(fotos, etiquetas * 2)


def test_lote_vacio_preserva_columnas():
    lote = pd.DataFrame(columns=["path", "content", "fecha_carpeta"])
    salidas = list(extraer_lote(iter([lote])))
    candidatos = list(candidatos_lote(iter(salidas)))[0]
    assert candidatos.empty
    assert "foto_origen" in candidatos.columns
