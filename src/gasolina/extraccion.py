"""Punto de entrada de la extracción de precios (dueño: Modelos).

ESTADO: STUB. Devuelve un dict con TODAS las claves del contrato 4.1
(docs/INSTRUCTIVO_GENERAL.md), los precios en None y "modo": "stub".

La API (src/gasolina/api/app.py) y el notebook 02_plata consumen esta función:
  - NO cambiar el nombre ni quitar claves del resultado.
  - Cuando el OCR real esté listo, cambiar MODO_EXTRACCION a "real" y devolver "modo": "real".
    /health reporta MODO_EXTRACCION.
"""

from __future__ import annotations

import time
from pathlib import Path

from gasolina import __version__
from gasolina.metadata import leer_metadata

MODO_EXTRACCION = "stub"

COMBUSTIBLES = ("diesel", "regular", "super", "vpower")

CLAVES_RESULTADO = (
    "archivo",
    "modo",
    "metadata",
    "ruta_a",
    "precios",
    "fuentes",
    "combustible_despachado",
    "validaciones",
    "score_confianza",
    "estrategia",
    "motor",
    "preproc",
    "segunda_pasada",
    "tiempo_ms",
    "version_modelo",
    "detecciones_crudas",
)


def extraer_precios(
    ruta: str | Path,
    motor: str = "rapidocr",
    preproc: str = "gris_clahe",
    estrategia: str = "fusion",
    referencia: dict | None = None,
    segunda_pasada: bool = False,
) -> dict:
    """Lee los 4 precios de una foto de bomba.

    Args:
        ruta: ruta a la imagen (JPG, PNG o HEIC).
        motor: "rapidocr" | "easyocr".
        preproc: "ninguno" | "gris_clahe" | "gris_clahe_x2" | "binarizado".
        estrategia: "solo_A" | "solo_B" | "fusion".
        referencia: precios de referencia MEM {"diesel", "regular", "super", ...} (opcional).
        segunda_pasada: OCR extra sobre la franja de pantallitas ampliada.

    Returns:
        dict del contrato 4.1. STUB: precios en None, "modo": "stub".
    """
    t0 = time.perf_counter()
    ruta = Path(ruta)
    metadata = leer_metadata(ruta)
    return {
        "archivo": ruta.name,
        "modo": MODO_EXTRACCION,
        "metadata": metadata,
        "ruta_a": {"total": None, "galones": None, "precio_a": None},
        "precios": dict.fromkeys(COMBUSTIBLES),
        "fuentes": dict.fromkeys(COMBUSTIBLES),
        "combustible_despachado": None,
        "validaciones": [
            {
                "nombre": "ocr_disponible",
                "estado": "advertencia",
                "mensaje": "Extracción en modo stub: el OCR real todavía no está implementado.",
            }
        ],
        "score_confianza": 0.0,
        "estrategia": estrategia,
        "motor": motor,
        "preproc": preproc,
        "segunda_pasada": segunda_pasada,
        "tiempo_ms": round((time.perf_counter() - t0) * 1000),
        "version_modelo": __version__,
        "detecciones_crudas": [],
    }
