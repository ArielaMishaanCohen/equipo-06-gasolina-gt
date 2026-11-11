"""Metadata EXIF (contrato 5.2, campo "metadata")."""

from pathlib import Path

import pytest

from gasolina.metadata import CLAVES_METADATA, leer_metadata, leer_metadata_bytes

FOTO = Path(__file__).resolve().parents[2] / "datos" / "IMG_8271.jpg"


def test_sin_exif_no_truena(tmp_path):
    from PIL import Image

    ruta = tmp_path / "x.png"
    Image.new("RGB", (40, 30)).save(ruta)
    m = leer_metadata(ruta)
    assert set(m) == set(CLAVES_METADATA)
    assert (m["ancho"], m["alto"]) == (40, 30)
    assert m["fecha_hora"] is None and m["lat"] is None


def test_bytes_que_no_son_imagen():
    m = leer_metadata_bytes(b"no soy una foto", "x.jpg")
    assert set(m) == set(CLAVES_METADATA) and m["archivo"] == "x.jpg" and m["ancho"] is None


@pytest.mark.skipif(not FOTO.is_file(), reason="foto de ejemplo no disponible")
def test_foto_real():
    m = leer_metadata(FOTO)
    assert m["fecha_hora"] == "2026-07-09T19:42:19"
    assert m["modelo_camara"] == "iPhone 14"
    assert m["lat"] == pytest.approx(14.56, abs=0.01)
    assert m["lon"] == pytest.approx(-90.46, abs=0.01)
    assert m["altitud"] == pytest.approx(1861.8, abs=0.5)
    assert (m["ancho"], m["alto"]) == (3024, 4032)
    assert leer_metadata_bytes(FOTO.read_bytes(), FOTO.name) == m
