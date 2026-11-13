"""Variación semanal y variables del modelo (contrato 5.4) en pandas (dueño: Datos).

Entrada: la serie semanal de precios de UNA fuente (en el pipeline, la del MEM) con las columnas
`semana_inicio` (martes), `combustible` y `precio_promedio`. Las semanas sin dato **no se rellenan
ni se interpolan**: todo lo que dependa de una semana ausente queda nulo.

Definiciones (iguales en `pipelines/03_gold.py`, el informe y la API):

- `precio_anterior`: precio de la semana inmediatamente anterior (`semana_inicio - 7 días`).
  Si esa semana no existe, es nulo (aunque haya semanas más viejas).
- `dif_q = precio_promedio - precio_anterior` (Q/galón, 2 decimales).
- `dif_pct = 100 * dif_q / precio_anterior` (porcentaje, 2 decimales).
- `direccion`: `sube` si `dif_q > umbral_q`, `baja` si `dif_q < -umbral_q` y, si no,
  `se_mantiene`. Nula si `dif_q` es nula.
- `var_q_k` (k = 1..4): `dif_q` de la semana `semana_inicio - 7 * (k - 1)`. `var_q_1` es la
  variación de la semana actual; las demás son las de las semanas previas. Nula si falta alguna
  de las semanas necesarias, así que queda nula durante las 4 semanas posteriores a un hueco.
- `prom_movil_4`: promedio de `precio_promedio` de las últimas 4 semanas consecutivas (incluida la
  actual); nulo si falta alguna.
- `dif_super_diesel`: precio super menos precio diésel de la misma semana (en las filas de todos los
  combustibles); nulo si falta alguno de los dos.
- `direccion_actual`: igual a `direccion`.
- `direccion_siguiente` (objetivo): `direccion` de la semana siguiente; nula en la última semana y
  cuando la semana siguiente no existe.
- `wti_var_1` (opcional): promedio semanal del WTI (USD/barril) menos el de la semana anterior;
  nulo si falta alguno de los dos promedios.
- `subsidio_activo` (opcional): 1, 0 o nulo según `eventos_subsidio`; ver `subsidio_activo_semanas`.
"""

from __future__ import annotations

import pandas as pd

UMBRAL_Q = 0.10
SEMANA = pd.Timedelta(days=7)

COLUMNAS_VARIACION = [
    "semana_inicio", "combustible", "precio_promedio", "precio_anterior", "dif_q", "dif_pct",
    "direccion", "umbral_q",
]
COLUMNAS_FEATURES = [
    "semana_inicio", "combustible", "var_q_1", "var_q_2", "var_q_3", "var_q_4", "prom_movil_4",
    "dif_super_diesel", "direccion_actual", "wti_var_1", "subsidio_activo", "direccion_siguiente",
]


def clasificar_direccion(dif_q, umbral_q: float = UMBRAL_Q):
    """`sube` / `baja` / `se_mantiene` según el umbral; None si `dif_q` es nulo."""
    if dif_q is None or pd.isna(dif_q):
        return None
    if dif_q > umbral_q:
        return "sube"
    if dif_q < -umbral_q:
        return "baja"
    return "se_mantiene"


def _fechas(serie) -> pd.Series:
    return pd.to_datetime(serie).dt.normalize()


def _solo_fecha(serie: pd.Series) -> pd.Series:
    return serie.dt.date


def _serie_semanal(precios: pd.DataFrame) -> pd.DataFrame:
    """Valida y normaliza: fechas a datetime, precio numérico, sin nulos, una fila por llave."""
    p = precios[["semana_inicio", "combustible", "precio_promedio"]].copy()
    p["semana_inicio"] = _fechas(p["semana_inicio"])
    p["precio_promedio"] = pd.to_numeric(p["precio_promedio"], errors="coerce")
    p = p.dropna(subset=["semana_inicio", "precio_promedio"])
    if p.duplicated(["semana_inicio", "combustible"]).any():
        raise ValueError("Hay más de una fila por semana y combustible: agrégalas antes "
                         "(una sola fuente por serie).")
    if (p["semana_inicio"].dt.weekday != 1).any():
        raise ValueError("`semana_inicio` debe ser martes (semanas de martes a lunes).")
    return p.sort_values(["combustible", "semana_inicio"]).reset_index(drop=True)


def construir_variacion(precios: pd.DataFrame, umbral_q: float = UMBRAL_Q) -> pd.DataFrame:
    """Tabla `variacion_semanal`: una fila por semana y combustible de la serie de entrada."""
    if precios is None or len(precios) == 0:
        return pd.DataFrame(columns=COLUMNAS_VARIACION)
    p = _serie_semanal(precios)
    previo = p.assign(semana_inicio=p["semana_inicio"] + SEMANA).rename(
        columns={"precio_promedio": "precio_anterior"})
    v = p.merge(previo, how="left", on=["semana_inicio", "combustible"])
    v["dif_q"] = (v["precio_promedio"] - v["precio_anterior"]).round(2)
    v["dif_pct"] = (100 * v["dif_q"] / v["precio_anterior"]).round(2)
    direccion = v["dif_q"].map(lambda d: clasificar_direccion(d, umbral_q)).astype(object)
    v["direccion"] = direccion.where(direccion.notna(), None)
    v["umbral_q"] = float(umbral_q)
    v = v.sort_values(["semana_inicio", "combustible"]).reset_index(drop=True)
    v["semana_inicio"] = _solo_fecha(v["semana_inicio"])
    return v[COLUMNAS_VARIACION]


def _al_calendario(serie: pd.Series) -> pd.Series:
    """Reindexa una serie con índice de martes a todas las semanas entre su mínimo y máximo."""
    if serie.empty:
        return serie
    return serie.reindex(pd.date_range(serie.index.min(), serie.index.max(), freq="7D"))


def wti_variacion_semanal(wti_semanal: pd.DataFrame | None) -> pd.Series:
    """Serie indexada por semana (martes) con el cambio del promedio semanal del WTI.

    Entrada: columnas `semana_inicio` y `wti_promedio`. Semanas sin dato -> nulo (no se rellenan).
    """
    if wti_semanal is None or len(wti_semanal) == 0:
        return pd.Series(dtype="float64")
    w = wti_semanal[["semana_inicio", "wti_promedio"]].copy()
    w["semana_inicio"] = _fechas(w["semana_inicio"])
    w["wti_promedio"] = pd.to_numeric(w["wti_promedio"], errors="coerce")
    s = w.dropna().drop_duplicates("semana_inicio").set_index("semana_inicio")["wti_promedio"]
    s = _al_calendario(s.sort_index())
    return (s - s.shift(1)).round(2)


def _fecha_o_nat(valor):
    """Fecha confirmada o NaT: vacío, None, NaN y "nan"/"none" significan "sin fecha confirmada"."""
    if valor is None or (isinstance(valor, float) and pd.isna(valor)) or valor is pd.NaT:
        return pd.NaT
    texto = str(valor).strip()
    if not texto or texto.lower() in ("nan", "none", "nat"):
        return pd.NaT
    return pd.to_datetime(texto)


def subsidio_activo_semanas(semanas, eventos_subsidio: pd.DataFrame | None) -> pd.Series:
    """`subsidio_activo` por semana (martes a lunes): 1, 0 o nulo, sin inventar fechas.

    `eventos_subsidio` trae `fecha_inicio` y `fecha_fin`; una fecha vacía significa "sin fecha
    confirmada" y no se reemplaza por ninguna suposición. Para una semana [martes, lunes]:

    - **0**: la semana termina antes del primer inicio confirmado de todos los eventos (todavía
      no había empezado ningún apoyo).
    - **1**: hay un evento con inicio y fin confirmados que se traslapa con la semana, o la
      semana contiene el inicio confirmado de un evento cuyo fin no está confirmado.
    - **nulo**: no está confirmado que haya apoyo ni que no lo haya: un evento con inicio
      confirmado y fin vacío ya empezado (semanas posteriores a la de inicio), o un evento sin
      inicio confirmado cuyo fin no es anterior a la semana.
    - **0** también cuando, ya empezado el primer apoyo, ningún evento está ni pudo estar vigente.

    Sin eventos, o sin ningún inicio confirmado, todo es nulo: no se sabe.
    """
    semanas = list(semanas)
    idx = pd.DatetimeIndex(_fechas(pd.Series(semanas))) if semanas else pd.DatetimeIndex([])
    if eventos_subsidio is None or len(eventos_subsidio) == 0:
        return pd.Series([pd.NA] * len(idx), index=idx, dtype="Int64")
    eventos = [(_fecha_o_nat(r["fecha_inicio"]), _fecha_o_nat(r["fecha_fin"]))
               for _, r in eventos_subsidio.iterrows()]
    inicios = [i for i, _ in eventos if pd.notna(i)]
    if not inicios:
        return pd.Series([pd.NA] * len(idx), index=idx, dtype="Int64")
    primer_inicio = min(inicios)

    out = []
    for ini_sem in idx:
        fin_sem = ini_sem + pd.Timedelta(days=6)
        if fin_sem < primer_inicio:
            out.append(0)
            continue
        confirmado = any(
            (pd.notna(i) and pd.notna(f) and i <= fin_sem and f >= ini_sem)
            or (pd.notna(i) and pd.isna(f) and ini_sem <= i <= fin_sem)
            for i, f in eventos)
        if confirmado:
            out.append(1)
            continue
        posible = any(
            (pd.notna(i) and pd.isna(f) and i < ini_sem)
            or (pd.isna(i) and pd.notna(f) and f >= ini_sem)
            or (pd.isna(i) and pd.isna(f))
            for i, f in eventos)
        out.append(pd.NA if posible else 0)
    return pd.Series(out, index=idx, dtype="Int64")


def construir_features(variacion: pd.DataFrame, wti_semanal: pd.DataFrame | None = None,
                       eventos_subsidio: pd.DataFrame | None = None) -> pd.DataFrame:
    """Tabla `features_modelo` a partir de la salida de `construir_variacion`.

    Una fila por semana y combustible de la serie. Los huecos de la serie no se rellenan: las
    variables que usan una semana ausente quedan nulas (ver el encabezado del módulo).
    """
    if variacion is None or len(variacion) == 0:
        return pd.DataFrame(columns=COLUMNAS_FEATURES)
    v = variacion.copy()
    v["semana_inicio"] = _fechas(v["semana_inicio"])

    trozos = []
    for comb, g in v.groupby("combustible"):
        g = g.set_index("semana_inicio").sort_index()
        dif = _al_calendario(g["dif_q"])
        precio = _al_calendario(g["precio_promedio"])
        direccion = _al_calendario(g["direccion"].astype(object))
        f = pd.DataFrame(index=precio.index)
        for k in range(1, 5):
            f[f"var_q_{k}"] = dif.shift(k - 1)
        f["prom_movil_4"] = precio.rolling(4, min_periods=4).mean().round(2)
        f["direccion_actual"] = direccion
        f["direccion_siguiente"] = direccion.shift(-1)
        f["combustible"] = comb
        trozos.append(f.loc[g.index])  # solo semanas con dato
    feat = pd.concat(trozos).rename_axis("semana_inicio").reset_index()

    pivote = v.pivot(index="semana_inicio", columns="combustible", values="precio_promedio")
    if {"super", "diesel"} <= set(pivote.columns):
        dsd = (pivote["super"] - pivote["diesel"]).round(2)
    else:
        dsd = pd.Series(dtype="float64")
    feat["dif_super_diesel"] = feat["semana_inicio"].map(dsd)

    wti = wti_variacion_semanal(wti_semanal)
    feat["wti_var_1"] = feat["semana_inicio"].map(wti) if len(wti) else float("nan")

    semanas = sorted(feat["semana_inicio"].unique())
    sub = subsidio_activo_semanas(semanas, eventos_subsidio)
    feat["subsidio_activo"] = feat["semana_inicio"].map(sub.to_dict()).astype("Int64")

    feat = feat.sort_values(["semana_inicio", "combustible"]).reset_index(drop=True)
    feat["semana_inicio"] = _solo_fecha(feat["semana_inicio"])
    for col in ("direccion_actual", "direccion_siguiente"):
        feat[col] = feat[col].astype(object).where(feat[col].notna(), None)
    return feat[COLUMNAS_FEATURES]
