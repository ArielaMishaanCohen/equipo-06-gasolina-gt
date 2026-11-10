"""Motores de OCR y preprocesamiento (dueño: Modelos).

ESTADO: STUB. Ver docs/INSTRUCTIVO_GENERAL.md, sección 8.1.2.

Diseño esperado:
  - Clase base OcrEngine con `leer(imagen_np) -> list[dict]`, cada detección:
        {"texto": str, "confianza": float, "bbox": (x1, y1, x2, y2)}
  - RapidOcrEngine: usa rapidocr_onnxruntime.RapidOCR() (motor principal, sin GPU ni internet).
  - EasyOcrEngine: import perezoso, allowlist "0123456789.", solo si easyocr está instalado
    (extra [easyocr]); se usa en los experimentos de MLflow, NO en producción.
  - preprocesar(imagen, preproc) con preproc ∈ PREPROCS. Reducir a ~1600 px de alto antes
    del OCR para que sea rápido.
"""

from __future__ import annotations

MOTORES = ("rapidocr", "easyocr")
PREPROCS = ("ninguno", "gris_clahe", "gris_clahe_x2", "binarizado")


class OcrEngine:
    """Interfaz común de los motores de OCR."""

    nombre = "base"

    def leer(self, imagen_np) -> list[dict]:
        raise NotImplementedError("OCR pendiente (Modelos, sección 8.1.2)")


class RapidOcrEngine(OcrEngine):
    nombre = "rapidocr"


class EasyOcrEngine(OcrEngine):
    nombre = "easyocr"


def crear_motor(nombre: str = "rapidocr") -> OcrEngine:
    """Fábrica de motores. STUB."""
    if nombre not in MOTORES:
        raise ValueError(f"Motor desconocido: {nombre}. Opciones: {MOTORES}")
    return RapidOcrEngine() if nombre == "rapidocr" else EasyOcrEngine()


def preprocesar(imagen_np, preproc: str = "gris_clahe"):
    """Aplica el preprocesamiento indicado. STUB: devuelve la imagen sin cambios."""
    if preproc not in PREPROCS:
        raise ValueError(f"Preprocesamiento desconocido: {preproc}. Opciones: {PREPROCS}")
    return imagen_np
