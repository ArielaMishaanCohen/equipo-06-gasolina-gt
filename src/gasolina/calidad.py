"""Reglas de calidad de Plata (contrato 5.3 del INSTRUCTIVO_GENERAL) (dueño: Datos).

Una lectura de precio es una fila con (al menos) estas columnas:
`fecha`, `combustible`, `precio_q_galon`, `modalidad`, `ubicacion`, `foto_origen`, `confianza`.

Reglas (en este orden de prioridad):

| regla                   | falla si                                                              |
| ----------------------- | --------------------------------------------------------------------- |
| `combustible_valido`    | el combustible no está en el catálogo (super, regular, diesel)        |
| `rango_precio`          | el precio no está en [min, max] Q/galón (config.yaml, 20 a 60)        |
| `fecha_no_futura`       | la fecha falta o es posterior a hoy (hora de Guatemala)               |
| `consistencia_gasolinas`| en la misma foto (y modalidad y ubicación) super <= regular           |
| `confianza_minima`      | la confianza falta o es menor que el mínimo (config.yaml, 0.5)        |

Además, una foto sin ningún precio legible (combustible y precio nulos) va a cuarentena con
`regla = motivo = "sin_precios_legibles"` y no se evalúan las demás reglas.

Una fila que incumple varias reglas sale UNA sola vez en los rechazados: `regla` es la primera
de la tabla (la de mayor prioridad) y `motivo` junta los mensajes de todas las que incumple,
separados por "; ". Los valores ausentes cuentan como incumplimiento de la regla que los necesita.

Salidas: `validos` y `rechazados` conservan todas las columnas de entrada; `rechazados` agrega
`regla` y `motivo`. En ambas, `modalidad` y `ubicacion` nulas/vacías pasan a `no_indica` (la
llave del MERGE de Plata no admite nulos) y `combustible` se normaliza a minúsculas sin espacios.

Hay dos versiones con la misma lógica y los mismos mensajes:
  - `aplicar_reglas(df_pandas)` para pruebas y trabajo local.
  - `aplicar_reglas_spark(df_spark)` (y `expresiones_reglas_spark`) para `02_silver`, sin pandas.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd

from gasolina.config import cargar_config

NO_INDICA = "no_indica"
SIN_PRECIOS = "sin_precios_legibles"
REGLAS = (
    "combustible_valido",
    "rango_precio",
    "fecha_no_futura",
    "consistencia_gasolinas",
    "confianza_minima",
)
TODAS_LAS_REGLAS = (SIN_PRECIOS, *REGLAS)


def _parametros(rango=None, confianza_min=None, combustibles=None, hoy=None):
    cfg = cargar_config()
    rango = rango or (cfg["calidad"]["rango_precio"]["min"], cfg["calidad"]["rango_precio"]["max"])
    if confianza_min is None:
        confianza_min = cfg["calidad"]["confianza_minima"]
    combustibles = tuple(combustibles or cfg["combustibles"])
    if hoy is None:
        zona = timezone(timedelta(hours=cfg["api"]["zona_horaria_utc"]))
        hoy = datetime.now(zona).date()
    elif isinstance(hoy, datetime):
        hoy = hoy.date()
    return (float(rango[0]), float(rango[1])), float(confianza_min), combustibles, hoy


# ---------------------------------------------------------------------------------------------
# pandas
# ---------------------------------------------------------------------------------------------


def _texto(serie: pd.Series) -> pd.Series:
    """Texto sin espacios; vacío o nulo -> NA."""
    s = serie.astype("string").str.strip()
    return s.mask(s == "")


def aplicar_reglas(df: pd.DataFrame, hoy=None, rango=None, confianza_min=None, combustibles=None):
    """Aplica las 5 reglas a un DataFrame de pandas -> (df_validos, df_rechazados).

    Los parámetros opcionales sustituyen a los de config.yaml: `hoy` (date), `rango` (min, max),
    `confianza_min` y `combustibles`.
    """
    (rmin, rmax), cmin, catalogo, hoy = _parametros(rango, confianza_min, combustibles, hoy)
    d = df.reset_index(drop=True).copy()
    original_comb = d["combustible"].copy()

    comb = _texto(d["combustible"]).str.lower()
    d["combustible"] = comb.astype(object).where(comb.notna(), None)
    for col in ("modalidad", "ubicacion"):
        t = _texto(d[col]) if col in d else pd.Series(pd.NA, index=d.index, dtype="string")
        d[col] = t.fillna(NO_INDICA).astype(object)

    precio = pd.to_numeric(d["precio_q_galon"], errors="coerce")
    fecha = pd.to_datetime(d["fecha"], errors="coerce").dt.date
    conf = pd.to_numeric(d["confianza"], errors="coerce")

    sin_precios = comb.isna() & precio.isna()

    fallas: dict[str, pd.Series] = {}
    motivos: dict[str, pd.Series] = {}

    # combustible_valido
    f = ~comb.isin(catalogo) | comb.isna()
    m = original_comb.map(
        lambda v: "combustible ausente" if pd.isna(v) or str(v).strip() == ""
        else f"combustible '{v}' fuera del catálogo ({', '.join(catalogo)})")
    fallas["combustible_valido"], motivos["combustible_valido"] = f, m

    # rango_precio
    f = precio.isna() | (precio < rmin) | (precio > rmax)
    m = precio.map(lambda p: "precio ausente" if pd.isna(p)
                   else f"precio {p:.2f} fuera de [{rmin:g}, {rmax:g}] Q/galón")
    fallas["rango_precio"], motivos["rango_precio"] = f, m

    # fecha_no_futura
    futura = fecha.map(lambda x: x is not pd.NaT and not pd.isna(x) and x > hoy).astype(bool)
    f = fecha.isna() | futura
    m = fecha.map(lambda x: "fecha ausente o inválida" if pd.isna(x)
                  else f"fecha {x} posterior a hoy ({hoy})")
    fallas["fecha_no_futura"], motivos["fecha_no_futura"] = f, m

    # consistencia_gasolinas: en una misma foto (modalidad y ubicación) super debe ser > regular
    f = pd.Series(False, index=d.index)
    m = pd.Series("", index=d.index, dtype=object)
    foto = d["foto_origen"] if "foto_origen" in d else pd.Series(pd.NA, index=d.index)
    base = pd.DataFrame({"foto": foto, "mod": d["modalidad"], "ubi": d["ubicacion"],
                         "comb": comb, "precio": precio})
    base = base[base["foto"].notna() & precio.notna() & comb.isin(["super", "regular"])]
    if not base.empty:
        llave = ["foto", "mod", "ubi"]
        sup = base[base["comb"] == "super"].groupby(llave)["precio"].min().rename("sup")
        reg = base[base["comb"] == "regular"].groupby(llave)["precio"].max().rename("reg")
        par = pd.concat([sup, reg], axis=1).dropna()
        par = par[par["sup"] <= par["reg"]]
        if not par.empty:
            marcas = base.join(par, on=llave, how="inner")
            f.loc[marcas.index] = True
            m.loc[marcas.index] = marcas.apply(
                lambda r: f"super ({r['sup']:.2f}) no es mayor que regular ({r['reg']:.2f}) "
                          "en la misma foto", axis=1)
    fallas["consistencia_gasolinas"], motivos["consistencia_gasolinas"] = f, m

    # confianza_minima
    f = conf.isna() | (conf < cmin)
    m = conf.map(lambda c: "confianza ausente" if pd.isna(c)
                 else f"confianza {c:.2f} < {cmin:g}")
    fallas["confianza_minima"], motivos["confianza_minima"] = f, m

    # Ensamblar regla y motivo por fila
    regla = pd.Series(None, index=d.index, dtype=object)
    motivo = pd.Series(None, index=d.index, dtype=object)
    for nombre in reversed(REGLAS):  # la de mayor prioridad se escribe al final
        pega = fallas[nombre] & ~sin_precios
        regla = regla.mask(pega, nombre)
    textos = pd.concat(
        [motivos[n].where(fallas[n] & ~sin_precios) for n in REGLAS], axis=1)
    motivo = textos.apply(lambda fila: "; ".join(x for x in fila if isinstance(x, str)) or None,
                          axis=1)
    regla = regla.mask(sin_precios, SIN_PRECIOS)
    motivo = motivo.mask(sin_precios, SIN_PRECIOS)

    rechaza = regla.notna()
    validos = d[~rechaza].reset_index(drop=True)
    rechazados = d[rechaza].assign(regla=regla[rechaza], motivo=motivo[rechaza])
    rechazados = rechazados.reset_index(drop=True)
    return validos, rechazados


def resumen_por_regla(rechazados: pd.DataFrame) -> dict[str, int]:
    """Filas rechazadas por regla (la de mayor prioridad por fila); incluye las que valen 0."""
    cuenta = rechazados["regla"].value_counts().to_dict() if len(rechazados) else {}
    return {r: int(cuenta.get(r, 0)) for r in TODAS_LAS_REGLAS}


# ---------------------------------------------------------------------------------------------
# Spark
# ---------------------------------------------------------------------------------------------


def expresiones_reglas_spark(hoy=None, rango=None, confianza_min=None, combustibles=None):
    """Expresiones de columnas de Spark con la misma lógica que `aplicar_reglas`.

    Devuelve un dict {regla: (columna_booleana_de_falla, columna_de_motivo)} más la clave
    `SIN_PRECIOS` con la condición de foto sin precios. Se evalúan sobre un DataFrame con las
    columnas de entrada (usan una ventana por foto para `consistencia_gasolinas`).
    """
    from pyspark.sql import Window
    from pyspark.sql import functions as F

    (rmin, rmax), cmin, catalogo, hoy = _parametros(rango, confianza_min, combustibles, hoy)

    comb = F.lower(F.trim(F.col("combustible").cast("string")))
    comb = F.when(comb == "", None).otherwise(comb)
    precio = F.col("precio_q_galon").cast("double")
    fecha = F.col("fecha").cast("date")
    conf = F.col("confianza").cast("double")
    modalidad = F.coalesce(F.when(F.trim(F.col("modalidad")) == "", None)
                           .otherwise(F.trim(F.col("modalidad"))), F.lit(NO_INDICA))
    ubicacion = F.coalesce(F.when(F.trim(F.col("ubicacion")) == "", None)
                           .otherwise(F.trim(F.col("ubicacion"))), F.lit(NO_INDICA))

    sin_precios = comb.isNull() & precio.isNull()

    ex = {SIN_PRECIOS: (sin_precios, F.lit(SIN_PRECIOS))}

    ex["combustible_valido"] = (
        comb.isNull() | ~comb.isin(list(catalogo)),
        F.when(comb.isNull(), F.lit("combustible ausente")).otherwise(
            F.format_string("combustible '%s' fuera del catálogo (" + ", ".join(catalogo) + ")",
                            F.col("combustible"))),
    )

    ex["rango_precio"] = (
        precio.isNull() | (precio < rmin) | (precio > rmax),
        F.when(precio.isNull(), F.lit("precio ausente")).otherwise(
            F.format_string(f"precio %.2f fuera de [{rmin:g}, {rmax:g}] Q/galón", precio)),
    )

    ex["fecha_no_futura"] = (
        fecha.isNull() | (fecha > F.lit(hoy)),
        F.when(fecha.isNull(), F.lit("fecha ausente o inválida")).otherwise(
            F.format_string("fecha %s posterior a hoy (" + str(hoy) + ")",
                            F.date_format(fecha, "yyyy-MM-dd"))),
    )

    ventana = Window.partitionBy(F.col("foto_origen"), modalidad, ubicacion)
    min_super = F.min(F.when((comb == "super") & precio.isNotNull(), precio)).over(ventana)
    max_regular = F.max(F.when((comb == "regular") & precio.isNotNull(), precio)).over(ventana)
    aplica = (F.col("foto_origen").isNotNull() & precio.isNotNull()
              & comb.isin("super", "regular") & min_super.isNotNull() & max_regular.isNotNull())
    ex["consistencia_gasolinas"] = (
        F.coalesce(aplica & (min_super <= max_regular), F.lit(False)),
        F.format_string("super (%.2f) no es mayor que regular (%.2f) en la misma foto",
                        min_super, max_regular),
    )

    ex["confianza_minima"] = (
        conf.isNull() | (conf < cmin),
        F.when(conf.isNull(), F.lit("confianza ausente")).otherwise(
            F.format_string(f"confianza %.2f < {cmin:g}", conf)),
    )
    # nulos en una condición cuentan como incumplimiento
    ex = {k: (F.coalesce(c, F.lit(True)) if k != "consistencia_gasolinas" else c, m)
          for k, (c, m) in ex.items()}
    return ex, comb, modalidad, ubicacion


def aplicar_reglas_spark(df, hoy=None, rango=None, confianza_min=None, combustibles=None):
    """Versión Spark de `aplicar_reglas`: DataFrame -> (validos, rechazados), sin pandas."""
    from pyspark.sql import functions as F

    ex, comb, modalidad, ubicacion = expresiones_reglas_spark(
        hoy, rango, confianza_min, combustibles)
    sin_precios = ex[SIN_PRECIOS][0]
    # Se evalúan sobre las columnas originales; luego se normalizan combustible, modalidad y
    # ubicación.
    falla = {r: F.when(~sin_precios, ex[r][0]).otherwise(F.lit(False)) for r in REGLAS}
    texto = {r: F.when(falla[r], ex[r][1]) for r in REGLAS}

    marcado = df.select(
        "*",
        F.array(*[F.when(falla[r], F.lit(r)) for r in REGLAS]).alias("_reglas"),
        F.concat_ws("; ", *[texto[r] for r in REGLAS]).alias("_motivos"),
        sin_precios.alias("_sin_precios"),
        comb.alias("_comb_norm"), modalidad.alias("_mod_norm"), ubicacion.alias("_ubi_norm"),
    )
    marcado = marcado.withColumn("_reglas", F.filter("_reglas", lambda x: x.isNotNull()))
    rechaza = F.col("_sin_precios") | (F.size("_reglas") > 0)

    columnas = df.columns
    normalizadas = [
        (F.col("_comb_norm").alias(c) if c == "combustible"
         else F.col("_mod_norm").alias(c) if c == "modalidad"
         else F.col("_ubi_norm").alias(c) if c == "ubicacion"
         else F.col(c))
        for c in columnas
    ]
    validos = marcado.filter(~rechaza).select(*normalizadas)
    rechazados = (
        marcado.filter(rechaza)
        .withColumn("regla", F.when(F.col("_sin_precios"), F.lit(SIN_PRECIOS))
                    .otherwise(F.col("_reglas")[0]))
        .withColumn("motivo", F.when(F.col("_sin_precios"), F.lit(SIN_PRECIOS))
                    .otherwise(F.col("_motivos")))
        .select(*normalizadas, "regla", "motivo")
    )
    return validos, rechazados
