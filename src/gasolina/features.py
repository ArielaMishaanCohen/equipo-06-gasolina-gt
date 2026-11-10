"""Construcción de features semanales para el pronóstico (dueño: Datos).

ESTADO: STUB. Ver docs/INSTRUCTIVO_GENERAL.md, sección 8.2.6 (features_forecast).

Función esperada:
  - construir_features(precios_mem, exogenas, subsidios, tipo_cambio=7.7) -> pd.DataFrame
    con una fila por (semana ISO, combustible):
      precio_mem (target), precio_lag1, precio_lag2, precio_lag4,
      fred_q_gal (serie FRED del combustible en Q/galón) y sus lags 1-2,
      wti_lag1, subsidio_activo (0/1), subsidio_monto.
    Gasolina Gulf (DGASUSGULF) para super/regular; ULSD (DDFUELUSGULF) para diesel.
"""

from __future__ import annotations

FEATURES = [
    "precio_lag1",
    "precio_lag2",
    "precio_lag4",
    "fred_q_gal_lag1",
    "fred_q_gal_lag2",
    "wti_lag1",
    "subsidio_activo",
    "subsidio_monto",
]


def construir_features(precios_mem, exogenas, subsidios, tipo_cambio: float = 7.7):
    """STUB."""
    raise NotImplementedError("Features pendientes (Datos, sección 8.2.6)")
