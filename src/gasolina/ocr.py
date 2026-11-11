"""Motores de OCR y preprocesamiento (dueño: Modelos).

  - `cargar_imagen(ruta_o_bytes)` -> np.ndarray RGB con la orientación EXIF aplicada (HEIC/JPG/PNG).
  - `OcrEngine.leer(imagen_np)` -> lista de detecciones
        {"texto": str, "confianza": float, "bbox": (x1, y1, x2, y2)}
    con coordenadas en píxeles de la imagen recibida.
  - RapidOcrEngine: rapidocr_onnxruntime (motor de producción, CPU, sin internet).
    IMPORTANTE: se llama con use_cls=False. El clasificador de ángulo voltea 180° las pantallitas
    de 7 segmentos ("26.29" sale como "6292"); las fotos ya vienen derechas por el EXIF.
  - EasyOcrEngine: import perezoso (extra [easyocr]); solo para experimentos en MLflow.
  - `preprocesar(imagen, preproc)` con preproc ∈ PREPROCS.
"""

from __future__ import annotations

import io
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

try:
    import pillow_heif

    pillow_heif.register_heif_opener()
except ImportError:  # pragma: no cover
    pillow_heif = None

MOTORES = ("rapidocr", "easyocr")
PREPROCS = ("ninguno", "gris_clahe", "gris_clahe_x2", "binarizado")


# --------------------------------------------------------------------------------------------
# Imagen
# --------------------------------------------------------------------------------------------
def cargar_imagen(fuente: str | Path | bytes) -> np.ndarray:
    """Abre una foto (ruta o bytes) y devuelve un arreglo RGB uint8 ya orientado."""
    if isinstance(fuente, (bytes, bytearray)):
        fuente = io.BytesIO(fuente)
    with Image.open(fuente) as im:
        im = ImageOps.exif_transpose(im)
        return np.asarray(im.convert("RGB"))


def redimensionar(imagen: np.ndarray, alto: int) -> tuple[np.ndarray, float]:
    """Escala la imagen a `alto` px. Devuelve (imagen, factor) con factor = nuevo / original."""
    import cv2

    h, w = imagen.shape[:2]
    if h == alto:
        return imagen, 1.0
    f = alto / h
    interp = cv2.INTER_AREA if f < 1 else cv2.INTER_CUBIC
    return cv2.resize(imagen, (max(1, round(w * f)), alto), interpolation=interp), f


def preprocesar(imagen_np: np.ndarray, preproc: str = "gris_clahe") -> np.ndarray:
    """Aplica el preprocesamiento indicado y devuelve una imagen RGB (3 canales) para el OCR.

    - ninguno: sin cambios.
    - gris_clahe: escala de grises + ecualización local de contraste (CLAHE).
    - gris_clahe_x2: lo anterior ampliado 2x (útil en recortes pequeños).
    - binarizado: grises + umbral de Otsu.
    """
    if preproc not in PREPROCS:
        raise ValueError(f"Preprocesamiento desconocido: {preproc}. Opciones: {PREPROCS}")
    if preproc == "ninguno":
        return imagen_np
    import cv2

    gris = cv2.cvtColor(imagen_np, cv2.COLOR_RGB2GRAY) if imagen_np.ndim == 3 else imagen_np
    if preproc in ("gris_clahe", "gris_clahe_x2"):
        out = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gris)
        if preproc == "gris_clahe_x2":
            out = cv2.resize(out, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    else:  # binarizado
        _, out = cv2.threshold(gris, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return cv2.cvtColor(out, cv2.COLOR_GRAY2RGB)


# --------------------------------------------------------------------------------------------
# Motores
# --------------------------------------------------------------------------------------------
class OcrEngine:
    """Interfaz común de los motores de OCR."""

    nombre = "base"

    def leer(self, imagen_np: np.ndarray) -> list[dict]:
        raise NotImplementedError


@lru_cache(maxsize=1)
def _rapidocr():
    from rapidocr_onnxruntime import RapidOCR

    return RapidOCR()


class RapidOcrEngine(OcrEngine):
    nombre = "rapidocr"

    def leer(self, imagen_np: np.ndarray) -> list[dict]:
        resultado, _ = _rapidocr()(imagen_np, use_cls=False)
        dets = []
        for caja, texto, conf in resultado or []:
            xs = [float(p[0]) for p in caja]
            ys = [float(p[1]) for p in caja]
            dets.append({"texto": str(texto), "confianza": float(conf),
                         "bbox": (min(xs), min(ys), max(xs), max(ys))})
        return dets


@lru_cache(maxsize=1)
def _easyocr():
    import easyocr  # extra opcional: pip install -e ".[easyocr]"

    return easyocr.Reader(["es", "en"], gpu=False, verbose=False)


class EasyOcrEngine(OcrEngine):
    nombre = "easyocr"

    def leer(self, imagen_np: np.ndarray) -> list[dict]:
        dets = []
        for caja, texto, conf in _easyocr().readtext(imagen_np):
            xs = [float(p[0]) for p in caja]
            ys = [float(p[1]) for p in caja]
            dets.append({"texto": str(texto), "confianza": float(conf),
                         "bbox": (min(xs), min(ys), max(xs), max(ys))})
        return dets


def crear_motor(nombre: str = "rapidocr") -> OcrEngine:
    """Fábrica de motores."""
    if nombre not in MOTORES:
        raise ValueError(f"Motor desconocido: {nombre}. Opciones: {MOTORES}")
    return RapidOcrEngine() if nombre == "rapidocr" else EasyOcrEngine()


def leer_escalado(motor: OcrEngine, imagen: np.ndarray, alto: int, preproc: str,
                  origen: tuple[float, float] = (0.0, 0.0)) -> list[dict]:
    """Corre el OCR sobre `imagen` reescalada a `alto` px y devuelve las bbox en coordenadas de la
    imagen original (más el desplazamiento `origen`, para recortes)."""
    reducida, f = redimensionar(imagen, alto)
    proc = preprocesar(reducida, preproc)
    fx = 2.0 if preproc == "gris_clahe_x2" else 1.0
    ox, oy = origen
    dets = motor.leer(proc)
    for d in dets:
        x1, y1, x2, y2 = d["bbox"]
        k = 1.0 / (f * fx)
        d["bbox"] = (ox + x1 * k, oy + y1 * k, ox + x2 * k, oy + y2 * k)
    return dets
