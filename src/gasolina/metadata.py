"""Metadata EXIF de las fotos (dueño: Modelos).

`leer_metadata(ruta)` y `leer_metadata_bytes(contenido, nombre)` devuelven un dict con EXACTAMENTE
las claves de CLAVES_METADATA (contrato 5.2, campo "metadata"):

  - fecha_hora: ISO 8601 (AAAA-MM-DDTHH:MM:SS), de DateTimeOriginal (o DateTime si no existe).
  - lat, lon: grados decimales con signo (S y W negativos), 6 decimales.
  - altitud: metros (negativa si GPSAltitudeRef = 1).
  - modelo_camara: ej. "iPhone 14".
  - ancho, alto: píxeles tal como se ve la foto (después de aplicar la orientación EXIF).
  - sha256 del archivo.

Soporta JPG, PNG y HEIC (pillow_heif). Si falta un campo va None; nunca lanza excepción por EXIF
incompleto o corrupto.
"""

from __future__ import annotations

import hashlib
import io
from datetime import datetime
from pathlib import Path

from PIL import Image

try:  # HEIC (fotos de iPhone)
    import pillow_heif

    pillow_heif.register_heif_opener()
except ImportError:  # pragma: no cover
    pillow_heif = None

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

# Etiquetas EXIF
_TAG_MODELO = 272
_TAG_ORIENTACION = 274
_TAG_DATETIME = 306
_IFD_EXIF = 0x8769
_TAG_DATETIME_ORIGINAL = 36867
_IFD_GPS = 0x8825


def sha256_archivo(ruta: str | Path, bloque: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        while chunk := f.read(bloque):
            h.update(chunk)
    return h.hexdigest()


def _a_float(valor) -> float | None:
    try:
        return float(valor)
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def _dms_a_decimal(dms, ref) -> float | None:
    """(grados, minutos, segundos) + 'N'/'S'/'E'/'W' -> grados decimales con signo."""
    try:
        g, m, s = (_a_float(x) for x in dms)
    except (TypeError, ValueError):
        return None
    if g is None or m is None or s is None:
        return None
    dec = g + m / 60 + s / 3600
    if isinstance(ref, bytes):
        ref = ref.decode(errors="ignore")
    if str(ref).strip().upper() in ("S", "W"):
        dec = -dec
    return round(dec, 6)


def _fecha_iso(texto) -> str | None:
    if not texto:
        return None
    texto = str(texto).strip().replace("\x00", "")
    for fmt in ("%Y:%m:%d %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(texto[:19], fmt).isoformat()
        except ValueError:
            continue
    return None


def _metadata_imagen(im: Image.Image, meta: dict) -> dict:
    try:
        exif = im.getexif()
    except Exception:  # noqa: BLE001 - EXIF corrupto: seguimos sin él
        exif = {}

    ancho, alto = im.size
    if exif and exif.get(_TAG_ORIENTACION) in (5, 6, 7, 8):  # rotada 90°: se ve al revés
        ancho, alto = alto, ancho
    meta["ancho"], meta["alto"] = int(ancho), int(alto)

    if not exif:
        return meta
    try:
        modelo = exif.get(_TAG_MODELO)
        meta["modelo_camara"] = str(modelo).strip("\x00 ").strip() or None if modelo else None
    except Exception:  # noqa: BLE001
        pass
    try:
        sub = exif.get_ifd(_IFD_EXIF)
        meta["fecha_hora"] = _fecha_iso(sub.get(_TAG_DATETIME_ORIGINAL)) or _fecha_iso(
            exif.get(_TAG_DATETIME)
        )
    except Exception:  # noqa: BLE001
        meta["fecha_hora"] = _fecha_iso(exif.get(_TAG_DATETIME))
    try:
        gps = exif.get_ifd(_IFD_GPS)
        if gps:
            if 2 in gps and 4 in gps:
                meta["lat"] = _dms_a_decimal(gps[2], gps.get(1, "N"))
                meta["lon"] = _dms_a_decimal(gps[4], gps.get(3, "E"))
            alt = _a_float(gps.get(6))
            if alt is not None:
                ref = gps.get(5, b"\x00")
                bajo_mar = ref in (1, b"\x01", "1")
                meta["altitud"] = round(-alt if bajo_mar else alt, 1)
    except Exception:  # noqa: BLE001
        pass
    return meta


def _leer(fuente, nombre: str, sha: str) -> dict:
    meta = dict.fromkeys(CLAVES_METADATA)
    meta["archivo"] = nombre
    meta["sha256"] = sha
    try:
        with Image.open(fuente) as im:
            _metadata_imagen(im, meta)
    except Exception:  # noqa: BLE001 - no es imagen o formato no soportado
        pass
    return meta


def leer_metadata(ruta: str | Path) -> dict:
    """Metadata del contrato 5.2 de una foto en disco."""
    ruta = Path(ruta)
    return _leer(ruta, ruta.name, sha256_archivo(ruta))


def leer_metadata_bytes(contenido: bytes, nombre: str = "foto") -> dict:
    """Igual que leer_metadata, para la columna `content` de bronze.fotos_precios."""
    return _leer(io.BytesIO(contenido), Path(nombre).name, hashlib.sha256(contenido).hexdigest())
