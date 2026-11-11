"""Reglas de extracción con detecciones sintéticas (sin imágenes ni OCR)."""

import pytest

from gasolina import reglas as R


def det(texto, x1, y1, x2, y2, conf=0.99):
    return {"texto": texto, "confianza": conf, "bbox": (x1, y1, x2, y2)}


@pytest.mark.parametrize("texto,esperado", [
    ("33.45", 33.45), ("3 3.4 5", 33.45), ("29:59", 29.59), ("Q33,45", 33.45),
    ("3709", 37.09), ("37,09", 37.09), ("basura", None), ("", None), ("12345678", None),
])
def test_normalizar_numero(texto, esperado):
    assert R.normalizar_numero(texto) == esperado


def test_es_precio_excluye_total_y_galones():
    assert R.es_precio("38.64") == 38.64
    assert R.es_precio("150.00") is None   # total de la venta
    assert R.es_precio("3.882") is None    # galones (3 decimales)
    assert R.es_precio("9.14") is None     # número cortado


@pytest.mark.parametrize("texto,esperado", [
    ("ION Diesel", "diesel"), ("JONDiesel", "diesel"), ("Súper", "super"), ("egular", "regular"),
    ("V-Power", "vpower"), ("FuelSave", None), ("COMPARTE TU EXPERIENCIA EN SHELL", None),
])
def test_detectar_combustible(texto, esperado):
    assert R.detectar_combustible(texto) == esperado


def test_ruta_a():
    dets = [det("Esta Venta", 880, 440, 970, 470), det("150.00", 840, 480, 1080, 590),
            det("3.882", 890, 590, 1035, 645), det("Galones", 890, 655, 970, 685)]
    a = R.leer_ruta_a(dets)
    assert a["total"] == 150.0 and a["galones"] == 3.882 and a["precio_a"] == 38.64


def _bomba_shell(invertida=False):
    """4 pantallitas con su etiqueta debajo. invertida: el otro lado de la bomba."""
    paneles = [("diesel", "33.96"), ("regular", "37.64"), ("super", "38.64"),
               ("V-Power", "39.14")]
    if invertida:
        paneles = paneles[::-1]
    pantallas, etiquetas = [], []
    for i, (nombre, precio) in enumerate(paneles):
        x = 600 + 200 * i
        pantallas.append({**det(precio, x, 1600, x + 100, 1650), "valor": float(precio)})
        etiquetas += R.etiquetas_combustible([det(nombre.capitalize(), x + 10, 1900,
                                                  x + 80, 1930)])
    return pantallas, etiquetas


@pytest.mark.parametrize("invertida", [False, True])
def test_asignar_por_etiqueta_respeta_el_orden_impreso(invertida):
    pantallas, etiquetas = _bomba_shell(invertida)
    asign = R.asignar_por_etiqueta(pantallas, etiquetas)
    por_precio = {p["valor"]: c for p, c in zip(pantallas, asign)}
    assert por_precio == {33.96: "diesel", 37.64: "regular", 38.64: "super", 39.14: "vpower"}


def test_inferir_faltante_por_secuencia():
    pantallas, etiquetas = _bomba_shell(invertida=True)
    # la etiqueta de diesel quedó tapada por la manguera
    etiquetas = [e for e in etiquetas if e["combustible"] != "diesel"]
    asign = R.asignar_por_etiqueta(pantallas, etiquetas)
    asign, inferido = R.inferir_faltantes(pantallas, asign, "shell")
    assert dict(zip([p["valor"] for p in pantallas], asign))[33.96] == "diesel"
    assert inferido.count(True) == 1


def test_fusion_corrige_un_digito_con_esta_venta():
    pantallas = [{"bbox": (0, 0, 1, 1), "valor": 32.79, "combustible": "super",
                  "votos": {"32.79": 2.9}},
                 {"bbox": (0, 0, 1, 1), "valor": 29.69, "combustible": "regular", "votos": {}}]
    out, despachado = R.fusionar({"precio_a": 32.19}, pantallas)
    assert despachado == "super"
    assert out[0]["valor"] == 32.19 and out[0]["fuente"] == "corregido_por_ruta_A"


def test_fusion_coincidencia_exacta():
    pantallas = [{"bbox": (0, 0, 1, 1), "valor": 27.29, "combustible": "super"}]
    out, despachado = R.fusionar({"precio_a": 27.29}, pantallas)
    assert out[0]["fuente"] == "ambas" and despachado == "super"


def test_reparar_orden_regular_mayor_que_super():
    pantallas = [
        {"valor": 42.09, "combustible": "super", "fuente": "ambas", "votos": {}},
        {"valor": 47.09, "combustible": "regular", "fuente": "ruta_B",
         "votos": {"47.09": 1.9, "41.09": 0.8}},
    ]
    R.reparar_orden(pantallas)
    assert pantallas[1]["valor"] == 41.09 and pantallas[1]["fuente"] == "corregido_por_reglas"


def test_validar_y_score():
    v = R.validar({"super": 38.64, "regular": 37.64, "diesel": 33.96},
                  {"precio_a": 38.64, "total": 150.0, "galones": 3.882})
    estados = {x["nombre"]: x["estado"] for x in v}
    assert estados["formato_y_rango"] == "ok" and estados["orden_gasolinas"] == "ok"
    assert estados["venta_entre_galones"] == "ok"
    assert all(set(x) == {"nombre", "estado", "mensaje"} for x in v)
    assert 0.9 <= R.score_confianza([0.95, 0.99], v) <= 1.0
    malo = R.validar({"super": 30.0, "regular": 31.0}, {"precio_a": None})
    assert {x["nombre"]: x["estado"] for x in malo}["orden_gasolinas"] == "falla"
    assert R.score_confianza([], malo) == 0.0


def test_clasificar_tipo_foto():
    assert R.clasificar_tipo_foto([det("Precio por galón", 0, 0, 10, 2)], 3) == "bomba"
    assert R.clasificar_tipo_foto([det("Shell", 0, 0, 10, 2)], 3) == "bomba"
    assert R.clasificar_tipo_foto([det("Gasolinera", 0, 0, 10, 2)], 2) == "rotulo"
    assert R.clasificar_tipo_foto([], 0) == "desconocido"
