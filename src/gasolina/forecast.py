"""Pronóstico semanal de precios (dueño: Modelos).

ESTADO: STUB. Ver docs/INSTRUCTIVO_GENERAL.md, sección 8.3.2.

Funciones esperadas:
  - baseline_ingenuo(df) -> predicción = precio de la semana actual.
  - entrenar(df, modelo="ridge"|"gbr") con validación temporal (sin mezclar futuro).
  - evaluar(y_real, y_pred) -> {"mae", "rmse", "mape"}.
  - predecir_proxima_semana(modelo, df) -> lista de
      {"combustible", "prediccion", "intervalo_inf", "intervalo_sup"}  (contrato 4.2).
La API de producción NO usa este módulo: solo lee artifacts/predicciones.json.
"""

from __future__ import annotations

MODELOS = ("baseline_ingenuo", "ridge", "gradient_boosting")


def entrenar(df, modelo: str = "ridge"):
    """STUB."""
    raise NotImplementedError("Pronóstico pendiente (Modelos, sección 8.3.2)")


def predecir_proxima_semana(modelo, df) -> list[dict]:
    """STUB."""
    raise NotImplementedError("Pronóstico pendiente (Modelos, sección 8.3.2)")
