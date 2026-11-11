from datetime import date
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
DATOS = RAIZ.parent / "datos"

VARIABLES_EXTERNAS = (
    "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "ORO_S3_PREFIX",
    "DATABRICKS_HOST", "DATABRICKS_TOKEN", "DATABRICKS_WAREHOUSE_ID",
)


@pytest.fixture(scope="session")
def oro_demo(tmp_path_factory):
    """Tablas Oro de ejemplo generadas en una carpeta temporal (fecha fija = reproducible)."""
    import sys

    sys.path.insert(0, str(RAIZ / "scripts"))
    from deltalake import write_deltalake
    from generar_oro_demo import generar

    destino = tmp_path_factory.mktemp("oro")
    for nombre, df in generar(30, date(2026, 11, 10)).items():
        write_deltalake(str(destino / nombre), df, mode="overwrite")
    return destino


@pytest.fixture
def cliente(tmp_path, monkeypatch, oro_demo):
    """TestClient sin S3 ni Databricks: lee las tablas Oro de ejemplo."""
    from fastapi.testclient import TestClient

    monkeypatch.setenv("GASOLINA_SIN_DOTENV", "1")
    for v in VARIABLES_EXTERNAS:
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setenv("ORO_DEMO_DIR", str(oro_demo))
    monkeypatch.setenv("LOGS_DIR", str(tmp_path / "logs"))
    monkeypatch.setenv("ENTORNO", "test")
    from gasolina.api.app import crear_app

    app = crear_app()
    app.state.tmp = tmp_path
    with TestClient(app) as c:
        yield c
