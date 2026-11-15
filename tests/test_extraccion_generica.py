"""Regresión de rótulos verticales y tablas MEM con OCR sintético."""

import io

import pytest
from PIL import Image

from gasolina import extraccion, reglas


@pytest.mark.parametrize("cabecera,tipo", [("PRECIOS", "rotulo"),
                                          ("Shell precio por galon", "rotulo"),
                                          ("MEM referencia precio por galon", "tabla_mem")])
def test_conserva_tres_filas_verticales_fuera_de_bombas(monkeypatch, cabecera, tipo):
    detecciones = [{"texto": cabecera, "bbox": (0, 0, 500, 20), "confianza": 0.99}]
    for y, combustible, precio in [(80, "Super", "33.45"), (400, "Regular", "32.45"),
                                    (720, "Diesel", "25.45")]:
        detecciones.extend([
            {"texto": combustible, "bbox": (0, y, 100, y + 20), "confianza": 0.99},
            {"texto": precio, "bbox": (120, y, 200, y + 20), "confianza": 0.99},
        ])
    monkeypatch.setattr(extraccion, "crear_motor", lambda *a: object())
    monkeypatch.setattr(extraccion, "leer_escalado", lambda *a: detecciones)
    contenido = io.BytesIO()
    Image.new("RGB", (600, 1000)).save(contenido, format="PNG")
    resultado = extraccion.extraer_precios(contenido.getvalue(), segunda_pasada=False)
    assert resultado["tipo_foto"] == tipo
    assert {r["combustible"] for r in resultado["registros"]} == {"super", "regular", "diesel"}


def test_modalidad_en_palabras_separadas():
    assert reglas.detectar_modalidad([{"texto": "AUTO"}, {"texto": "SERVICIO"}]) == "autoservicio"


def test_combustible_y_precio_en_misma_deteccion():
    deteccion = {"texto": "SUPER Q33,45", "bbox": (0, 0, 200, 20), "confianza": 0.99}
    candidatos = reglas.candidatos_precio([deteccion])
    assert candidatos[0]["valor"] == 33.45
    assert reglas.asignar_por_cercania(
        candidatos, reglas.etiquetas_combustible([deteccion])) == ["super"]
