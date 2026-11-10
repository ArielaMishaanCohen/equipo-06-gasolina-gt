import io
import json
import shutil

import pytest
from conftest import DATOS, RAIZ

from gasolina.extraccion import CLAVES_RESULTADO

FOTO = DATOS / "IMG_8271.jpg"


def _jpg_sintetico() -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (64, 48), (200, 30, 40)).save(buf, format="JPEG")
    return buf.getvalue()


def test_health_con_artifacts_demo(cliente):
    r = cliente.get("/health")
    assert r.status_code == 200
    h = r.json()
    assert h["status"] == "ok"
    assert h["origen_artifacts"] == "demo"
    assert h["modo_extraccion"] in ("stub", "real")
    assert set(h["artifacts"]) == {
        "ocr_config.json", "reglas.json", "forecast_meta.json",
        "predicciones.json", "historico.json", "monitoreo.json",
    }
    assert all(a["cargado"] for a in h["artifacts"].values())


def test_pagina(cliente):
    r = cliente.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]


def test_pronostico(cliente):
    r = cliente.get("/pronostico")
    assert r.status_code == 200
    p = r.json()
    assert p["disponible"] is True
    assert p["predicciones"]


def test_historico_metricas_monitoreo(cliente):
    assert cliente.get("/historico").json()["disponible"] is True
    assert cliente.get("/metricas").status_code == 200
    prod = cliente.get("/monitoreo/produccion").json()
    assert prod["disponible"] is False  # aún no hay logs
    assert cliente.get("/monitoreo/modelo").json()["disponible"] is True


def test_extraer_rechaza_no_imagen(cliente):
    r = cliente.post("/extraer", files={"foto": ("nota.txt", b"hola", "text/plain")})
    assert r.status_code == 400
    r = cliente.post("/extraer", files={"foto": ("falsa.jpg", b"no soy jpg", "image/jpeg")})
    assert r.status_code == 400


def _verificar_extraccion(cliente, nombre, contenido):
    r = cliente.post("/extraer", files={"foto": (nombre, contenido, "image/jpeg")})
    assert r.status_code == 200, r.text
    res = r.json()
    assert set(res) == set(CLAVES_RESULTADO)
    assert res["archivo"] == nombre
    assert res["metadata"]["archivo"] == nombre
    assert res["detecciones_crudas"] == []

    # Log del contrato 4.3
    logs = list((cliente.app.state.tmp / "logs").glob("predicciones_*.jsonl"))
    assert len(logs) == 1
    linea = json.loads(logs[0].read_text().splitlines()[-1])
    assert linea["archivo"] == nombre
    assert linea["entorno"] == "test"
    assert linea["origen_artifacts"] == "demo"

    assert cliente.get("/metricas").json()["total"] == 1
    assert cliente.get("/monitoreo/produccion").json()["disponible"] is True
    return res


def test_extraer_imagen_sintetica(cliente):
    _verificar_extraccion(cliente, "sintetica.jpg", _jpg_sintetico())


@pytest.mark.skipif(not FOTO.is_file(), reason="no está ../datos/IMG_8271.jpg")
def test_extraer_foto_real(cliente):
    res = _verificar_extraccion(cliente, FOTO.name, FOTO.read_bytes())
    assert len(res["metadata"]["sha256"]) == 64


def test_recarga_artifacts_sin_reiniciar(cliente):
    """Simula un `gasolina-sync descargar`: los JSON nuevos se usan sin reiniciar la API."""
    destino = cliente.app.state.tmp / "artifacts"
    shutil.copytree(RAIZ / "artifacts_demo", destino)
    pred = json.loads((destino / "predicciones.json").read_text())
    pred["origen"] = "databricks"
    pred["semana_objetivo"] = "2026-W99"
    (destino / "predicciones.json").write_text(json.dumps(pred))

    assert cliente.get("/health").json()["origen_artifacts"] == "databricks"
    assert cliente.get("/pronostico").json()["semana_objetivo"] == "2026-W99"
