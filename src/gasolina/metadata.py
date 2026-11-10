"""Metadata EXIF de las fotos (dueño: Modelos).

ESTADO: STUB. Por ahora solo `archivo` y `sha256` son reales; el resto va en None.

Lo que falta implementar (ver docs/INSTRUCTIVO_GENERAL.md, sección 8.1.1):
  - fecha_hora: ISO 8601, de DateTimeOriginal (o DateTime si no existe).
  - lat, lon: decimales con signo, convertidos desde grados/minutos/segundos del EXIF GPS
    (S y W son negativos). Ej.: 14.5600, -90.4628.
  - altitud: metros (float).
  - modelo_camara: ej. "iPhone 14".
  - ancho, alto: píxeles de la imagen.
  - Soportar JPG y HEIC (registrar pillow_heif). Si falta algún campo: None, nunca excepción.

Las claves devueltas deben ser EXACTAMENTE las de CLAVES_METADATA (contrato 4.1).
"""

from __future__ import annotations

import hashlib
from pathlib import Path

CLAVES_METADATA = (
    "archivo",
    "fecha_hora",
    "lat",
    "lon",
    "altitud",
    "modelo_camara",
    "ancho",
    "alto",
    "sha256",
)


def sha256_archivo(ruta: str | Path, bloque: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        while chunk := f.read(bloque):
            h.update(chunk)
    return h.hexdigest()


def leer_metadata(ruta: str | Path) -> dict:
    """Devuelve el dict de metadata del contrato 4.1 (STUB: solo archivo y sha256 reales)."""
    ruta = Path(ruta)
    meta = dict.fromkeys(CLAVES_METADATA)
    meta["archivo"] = ruta.name
    meta["sha256"] = sha256_archivo(ruta)
    return meta
