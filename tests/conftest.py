from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
DATOS = RAIZ.parent / "datos"


@pytest.fixture
def cliente(tmp_path, monkeypatch):
    """TestClient con ARTIFACTS_DIR vacío (=> artifacts demo) y logs en una carpeta temporal."""
    from fastapi.testclient import TestClient

    monkeypatch.setenv("ARTIFACTS_DIR", str(tmp_path / "artifacts"))
    monkeypatch.setenv("LOGS_DIR", str(tmp_path / "logs"))
    monkeypatch.setenv("ARTIFACTS_DEMO_DIR", str(RAIZ / "artifacts_demo"))
    monkeypatch.setenv("ENTORNO", "test")
    from gasolina.api.app import crear_app

    app = crear_app()
    app.state.tmp = tmp_path
    with TestClient(app) as c:
        yield c
