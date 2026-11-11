"""Extracción de precios de una foto (dueño: Modelos).

ESTADO: STUB. Devuelve un dict con TODAS las claves del contrato 5.2
(docs/instructivos/INSTRUCTIVO_GENERAL.md) y "registros" vacío, con "modo": "stub".

Lo consume pipelines/02_silver.py (una fila de silver.precios por registro).
  - NO cambiar el nombre ni quitar claves del resultado.
  - Cuando el OCR real esté listo, cambiar MODO_EXTRACCION a "real".

Lo que sabemos de las fotos (ver la guía de Modelos, sección 3.1): bombas Shell y Puma, el orden
de los combustibles cambia entre bombas, así que cada precio se asigna por la etiqueta impresa
("Diesel", "Regular", "Super") y no por la posición. V-Power se descarta.
"""

from __future__ import annotations

import time
from pathlib import Path

from gasolina import __version__
from gasolina.metadata import leer_metadata

MODO_EXTRACCION = "stub"

COMBUSTIBLES = ("super", "regular", "diesel")
MODALIDADES = ("autoservicio", "servicio_completo", None)
TIPOS_FOTO = ("rotulo", "bomba", "tabla_mem", "desconocido")

CLAVES_RESULTADO = (
    "archivo",
    "modo",
    "metadata",
    "registros",
    "tipo_foto",
    "validaciones",
    "score_confianza",
    "motor",
    "preproc",
    "tiempo_ms",
    "version_modelo",
    "detecciones_crudas",
)

CLAVES_REGISTRO = (
    "combustible",
    "precio_q_galon",
    "modalidad",
    "ubicacion",
    "confianza",
    "texto_fuente",
)


def extraer_precios(
    ruta: str | Path,
    motor: str = "rapidocr",
    preproc: str = "gris_clahe",
    fecha_carpeta: str | None = None,
) -> dict:
    """Lee los precios de una foto (HEIC, JPG o PNG).

    Args:
        ruta: ruta a la imagen.
        motor: "rapidocr" | "easyocr".
        preproc: "ninguno" | "gris_clahe" | "gris_clahe_x2" | "binarizado".
        fecha_carpeta: fecha de respaldo (AAAA-MM-DD) si la foto no trae EXIF.

    Returns:
        dict del contrato 5.2. STUB: "registros" vacío y "modo": "stub".
    """
    t0 = time.perf_counter()
    ruta = Path(ruta)
    return {
        "archivo": ruta.name,
        "modo": MODO_EXTRACCION,
        "metadata": leer_metadata(ruta),
        "registros": [],
        "tipo_foto": "desconocido",
        "validaciones": [
            {
                "nombre": "ocr_disponible",
                "estado": "advertencia",
                "mensaje": "Extracción en modo stub: el OCR real todavía no está implementado.",
            }
        ],
        "score_confianza": 0.0,
        "motor": motor,
        "preproc": preproc,
        "tiempo_ms": round((time.perf_counter() - t0) * 1000),
        "version_modelo": __version__,
        "detecciones_crudas": [],
    }
