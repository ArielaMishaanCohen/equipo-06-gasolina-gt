"""Punto de entrada de la API (FastAPI).

El código vive en el paquete `gasolina` (src/gasolina/api/app.py) para que los notebooks de
Databricks y la API compartan la misma configuración. Formas de arrancarla:

    gasolina-api                                    # entrypoint del paquete (puerto de PUERTO)
    uvicorn api.main:app --host 0.0.0.0 --port 8006 # desde la raíz del repo
"""

from gasolina.api.app import app  # noqa: F401
