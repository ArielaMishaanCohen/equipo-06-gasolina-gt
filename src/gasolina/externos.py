"""Fuentes externas: MEM (PDF) y FRED (CSV) (dueño: Datos).

ESTADO: STUB. Ver docs/INSTRUCTIVO_GENERAL.md, sección 8.2.4.

Funciones esperadas:
  - parsear_informe_mem(ruta_pdf) -> pd.DataFrame largo con columnas
      fecha (date), combustible (super|regular|diesel), precio_promedio, fuente_pdf.
    Usa pdfplumber; si una tabla no se puede parsear, warning y sigue.
  - consolidar_mem(rutas) -> DataFrame sin duplicados (misma fecha y combustible: gana el
    informe más reciente).
  - descargar_fred(serie, destino) -> Path del CSV (DGASUSGULF, DDFUELUSGULF, DCOILWTICO).
  - leer_fred(ruta_csv) -> DataFrame (fecha, serie, valor) con "." y vacíos como NaN.
"""

from __future__ import annotations

URL_FRED = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={serie}"
SERIES_FRED = ("DGASUSGULF", "DDFUELUSGULF", "DCOILWTICO")


def parsear_informe_mem(ruta_pdf):
    """STUB."""
    raise NotImplementedError("Parser MEM pendiente (Datos, sección 8.2.4)")


def descargar_fred(serie: str, destino):
    """STUB."""
    raise NotImplementedError("Descarga FRED pendiente (Datos, sección 8.2.4)")


def leer_fred(ruta_csv):
    """STUB."""
    raise NotImplementedError("Lectura FRED pendiente (Datos, sección 8.2.4)")
