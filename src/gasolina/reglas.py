"""Reglas de negocio: normalización, asignación, validaciones, fusión A+B (dueño: Modelos).

ESTADO: STUB. Ver docs/INSTRUCTIVO_GENERAL.md, secciones 1.5 y 8.1.2.

Funciones esperadas:
  - normalizar_numero(texto) -> float | None
      quitar espacios, "," -> ".", 4 dígitos sin punto -> insertar punto antes de los 2 últimos.
  - candidatos_precio(detecciones, rango) -> lista de detecciones con 2 decimales en rango
      (excluye el total de venta > 60 y los galones con 3 decimales).
  - asignar_ruta_b(candidatos) -> {"diesel", "regular", "super", "vpower"} ordenando por x
      el grupo de 4 que estén en la misma fila.
  - leer_ruta_a(detecciones) -> {"total", "galones", "precio_a"}.
  - validar(precios, ruta_a, reglas, referencia) -> lista de
      {"nombre", "estado": "ok"|"falla"|"advertencia", "mensaje"} con:
      formato_y_rango, orden_gasolinas, diferencias_tipicas, venta_entre_galones, referencia_mem.
  - fusionar(ruta_a, ruta_b, reglas) -> (precios, fuentes, combustible_despachado)
      fuentes ∈ FUENTES.
  - score_confianza(confianzas_ocr, validaciones) -> float en [0, 1].
"""

from __future__ import annotations

FUENTES = ("ruta_A", "ruta_B", "ambas", "corregido_por_ruta_A", "inferido")
ESTADOS = ("ok", "falla", "advertencia")
ESTRATEGIAS = ("solo_A", "solo_B", "fusion")


def normalizar_numero(texto: str) -> float | None:
    """STUB: '3709' -> 37.09, '37,09' -> 37.09, basura -> None."""
    raise NotImplementedError("Reglas pendientes (Modelos, sección 8.1.2)")


def validar(precios: dict, ruta_a: dict, reglas: dict, referencia: dict | None = None) -> list:
    """STUB: devuelve la lista de validaciones del contrato 4.1."""
    raise NotImplementedError("Reglas pendientes (Modelos, sección 8.1.2)")


def fusionar(ruta_a: dict, ruta_b: dict, reglas: dict) -> tuple[dict, dict, str | None]:
    """STUB: fusión de ruta A (Esta Venta) y ruta B (pantallitas)."""
    raise NotImplementedError("Reglas pendientes (Modelos, sección 1.5)")
