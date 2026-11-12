# Databricks notebook source
# MAGIC %md
# MAGIC # 03_gold — Indicadores, variables, modelo y predicción (Fase 3)
# MAGIC
# MAGIC **ESQUELETO.** Partes: (1) `precio_semanal`, `variacion_semanal` y `features_modelo` —
# MAGIC **Datos**; (2) entrenamiento con MLflow, `predicciones` y `metricas_modelo` — **Modelos**.
# MAGIC Contrato 5.4 de `docs/instructivos/INSTRUCTIVO_GENERAL.md`: la API lee estas tablas de
# MAGIC `s3://cc3105-au-869227452861-us-east-2-an/equipo6/gold/<tabla>/`, así que los nombres de
# MAGIC columnas tienen que ser exactamente esos.

# COMMAND ----------

# MAGIC %pip install /Workspace/Users/TU_CORREO/gasolina-mlops

# COMMAND ----------

dbutils.library.restartPython()

# COMMAND ----------

dbutils.widgets.text("catalogo", "workspace")
dbutils.widgets.text("esquema_bronze", "equipo6_bronze")
dbutils.widgets.text("esquema_silver", "equipo6_silver")
dbutils.widgets.text("esquema_gold", "equipo6_gold")
dbutils.widgets.text("ruta_equipo_oro", "s3://cc3105-au-869227452861-us-east-2-an/equipo6")
dbutils.widgets.text("umbral_q", "0.10")
dbutils.widgets.text("modalidad_mem", "autoservicio")

CATALOGO = dbutils.widgets.get("catalogo")
BRONZE = f"{CATALOGO}.{dbutils.widgets.get('esquema_bronze')}"
SILVER = f"{CATALOGO}.{dbutils.widgets.get('esquema_silver')}"
GOLD = f"{CATALOGO}.{dbutils.widgets.get('esquema_gold')}"
RUTA_EQUIPO_ORO = dbutils.widgets.get("ruta_equipo_oro").rstrip("/")
RUTA_GOLD = f"{RUTA_EQUIPO_ORO}/gold"  # las tablas viven en <ruta_equipo_oro>/gold/<tabla>/
UMBRAL_Q = float(dbutils.widgets.get("umbral_q"))
MODALIDAD_MEM = dbutils.widgets.get("modalidad_mem")


def _lit(texto: str) -> str:
    """Texto como literal SQL entre comillas simples."""
    return "'" + texto.replace("\\", "\\\\").replace("'", "\\'") + "'"


def guardar_oro(df, tabla: str, comentario: str, columnas: dict | None = None):
    """Escribe una tabla Oro externa en RUTA_GOLD/<tabla> (overwrite = idempotente) y le pone
    COMMENT a la tabla y, si se pasan, a cada columna."""
    (df.write.format("delta").mode("overwrite").option("overwriteSchema", "true")
       .option("path", f"{RUTA_GOLD}/{tabla}").saveAsTable(f"{GOLD}.{tabla}"))
    spark.sql(f"COMMENT ON TABLE {GOLD}.{tabla} IS {_lit(comentario)}")
    for columna, texto in (columnas or {}).items():
        spark.sql(f"ALTER TABLE {GOLD}.{tabla} ALTER COLUMN `{columna}` COMMENT {_lit(texto)}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Indicadores y variables (Datos)
# MAGIC
# MAGIC Contrato 5.4. **Semana de martes a lunes**: `semana_inicio = fecha - ((dayofweek(fecha) - 3 + 7) % 7)`
# MAGIC (en Spark `dayofweek` da 1 = domingo y 3 = martes).
# MAGIC
# MAGIC | Tabla | Qué es |
# MAGIC | --- | --- |
# MAGIC | `precio_semanal` | Promedio, mínimo, máximo y n por semana y combustible. `fuente = fotos` (de `silver.precios`) y `fuente = mem` (de `silver.mem_referencia`) en filas separadas. |
# MAGIC | `variacion_semanal` | Cambio contra la **semana inmediatamente anterior** y `direccion` con `umbral_q`. |
# MAGIC | `features_modelo` | Variables del modelo y objetivo `direccion_siguiente`. |
# MAGIC
# MAGIC Decisiones:
# MAGIC - `variacion_semanal` y `features_modelo` se calculan sobre la serie del **MEM**, que es la única
# MAGIC   con historia suficiente; las fotos entran solo en `precio_semanal`. Si `silver.precios` está
# MAGIC   vacía, todo corre igual con el MEM.
# MAGIC - **Las semanas faltantes no se rellenan ni se interpolan.** La variación contra una semana ausente
# MAGIC   es nula, `var_q_1` a `var_q_4` y `prom_movil_4` quedan nulos mientras su ventana incluya un hueco y
# MAGIC   `direccion_siguiente` es nula si falta la semana siguiente.
# MAGIC - `subsidio_activo` y `wti_var_1` son opcionales: sin tabla de eventos o de FRED quedan nulos.
# MAGIC   Una fecha vacía en `eventos_subsidio_raw` significa **sin fecha confirmada** y no se inventa.
# MAGIC - La lógica de variación y variables está en `gasolina.features` (pandas, con pruebas).

# COMMAND ----------

import math
from datetime import date

import pandas as pd
from pyspark.sql import functions as F
from pyspark.sql.types import (DateType, DoubleType, IntegerType, LongType, StringType, StructField,
                               StructType)

from gasolina import features

ESQ_PRECIO = StructType([
    StructField("semana_inicio", DateType()), StructField("semana_fin", DateType()),
    StructField("combustible", StringType()), StructField("precio_promedio", DoubleType()),
    StructField("precio_min", DoubleType()), StructField("precio_max", DoubleType()),
    StructField("n_registros", LongType()), StructField("fuente", StringType()),
])
ESQ_VARIACION = StructType([
    StructField("semana_inicio", DateType()), StructField("combustible", StringType()),
    StructField("precio_promedio", DoubleType()), StructField("precio_anterior", DoubleType()),
    StructField("dif_q", DoubleType()), StructField("dif_pct", DoubleType()),
    StructField("direccion", StringType()), StructField("umbral_q", DoubleType()),
])
ESQ_FEATURES = StructType([
    StructField("semana_inicio", DateType()), StructField("combustible", StringType()),
    StructField("var_q_1", DoubleType()), StructField("var_q_2", DoubleType()),
    StructField("var_q_3", DoubleType()), StructField("var_q_4", DoubleType()),
    StructField("prom_movil_4", DoubleType()), StructField("dif_super_diesel", DoubleType()),
    StructField("direccion_actual", StringType()), StructField("wti_var_1", DoubleType()),
    StructField("subsidio_activo", IntegerType()), StructField("direccion_siguiente", StringType()),
])


def semana_martes(c):
    """Martes que inicia la semana martes-lunes de la fecha `c` (contrato 5.4)."""
    return F.date_sub(c, (F.dayofweek(c) - 3 + 7) % 7)


def _py(v):
    """Valor de pandas/numpy -> valor de Python (nulos -> None) para createDataFrame."""
    if v is None or v is pd.NA or v is pd.NaT or (isinstance(v, float) and math.isnan(v)):
        return None
    return v.item() if hasattr(v, "item") and not isinstance(v, date) else v


def a_spark(pdf: pd.DataFrame, esquema: StructType):
    filas = [tuple(_py(v) for v in fila) for fila in pdf[esquema.fieldNames()].itertuples(
        index=False, name=None)]
    return spark.createDataFrame(filas, esquema)


def tabla_vacia_o_ausente(tabla: str) -> bool:
    return (not spark.catalog.tableExists(tabla)) or spark.table(tabla).limit(1).count() == 0

# COMMAND ----------

# MAGIC %md ### 1.1 `gold.precio_semanal`

# COMMAND ----------

def agregado_semanal(df, col_fecha: str, col_precio: str, fuente: str):
    """Una fila por semana (martes a lunes) y combustible, con promedio, mínimo, máximo y n."""
    return (
        df.filter(F.col(col_fecha).isNotNull() & F.col(col_precio).isNotNull())
        .withColumn("semana_inicio", semana_martes(F.col(col_fecha)))
        .groupBy("semana_inicio", "combustible")
        .agg(F.round(F.avg(col_precio), 2).cast("double").alias("precio_promedio"),
             F.min(col_precio).cast("double").alias("precio_min"),
             F.max(col_precio).cast("double").alias("precio_max"),
             F.count(F.lit(1)).cast("long").alias("n_registros"))
        .withColumn("semana_fin", F.date_add("semana_inicio", 6))
        .withColumn("fuente", F.lit(fuente))
        .select(*ESQ_PRECIO.fieldNames())
    )


T_FOTOS, T_MEM = f"{SILVER}.precios", f"{SILVER}.mem_referencia"

if spark.catalog.tableExists(T_FOTOS):
    fotos_sem = agregado_semanal(spark.table(T_FOTOS), "fecha", "precio_q_galon", "fotos")
else:
    print(f"⚠️ No existe {T_FOTOS}: precio_semanal sin filas de fotos.")
    fotos_sem = spark.createDataFrame([], ESQ_PRECIO)

if spark.catalog.tableExists(T_MEM):
    mem_sem = agregado_semanal(
        spark.table(T_MEM).filter(F.col("modalidad") == MODALIDAD_MEM),
        "semana_inicio", "precio_q_galon", "mem")
else:
    print(f"⚠️ No existe {T_MEM}: precio_semanal sin filas del MEM (corre 02_silver).")
    mem_sem = spark.createDataFrame([], ESQ_PRECIO)

precio_semanal = fotos_sem.unionByName(mem_sem).orderBy("fuente", "semana_inicio", "combustible").cache()
print("precio_semanal:", precio_semanal.groupBy("fuente").count().collect())

# COMMAND ----------

# MAGIC %md
# MAGIC ### 1.2 `gold.variacion_semanal` y 1.3 `gold.features_modelo`
# MAGIC
# MAGIC Se calculan en pandas (`gasolina.features`) sobre la serie del MEM: son unas cientos de filas.
# MAGIC Fuentes opcionales: `bronze.fred_raw` (WTI, promedio semanal) y `bronze.eventos_subsidio_raw`.

# COMMAND ----------

serie_mem = (precio_semanal.filter("fuente = 'mem'")
             .select("semana_inicio", "combustible", "precio_promedio").toPandas())
variacion_pd = features.construir_variacion(serie_mem, UMBRAL_Q)

# WTI de FRED (opcional): promedio semanal martes-lunes de las observaciones disponibles
T_FRED = f"{BRONZE}.fred_raw"
wti_pd = None
if not tabla_vacia_o_ausente(T_FRED):
    fred = spark.table(T_FRED)
    col_fecha, col_valor = [c for c in fred.columns if not c.startswith("_")][:2]
    wti_pd = (
        fred.select(
            F.try_to_timestamp(F.col(f"`{col_fecha}`"), F.lit("yyyy-MM-dd")).cast("date").alias("fecha"),
            F.expr(f"try_cast(`{col_valor}` as double)").alias("valor"))  # "." (feriado) -> NULL
        .filter("fecha IS NOT NULL AND valor IS NOT NULL")
        .withColumn("semana_inicio", semana_martes(F.col("fecha")))
        .groupBy("semana_inicio").agg(F.avg("valor").alias("wti_promedio")).toPandas()
    )
else:
    print(f"⚠️ {T_FRED} no existe o está vacía: wti_var_1 queda nulo.")

# Eventos del subsidio (opcional): fecha vacía = sin fecha confirmada (no se inventa)
T_EVENTOS = f"{BRONZE}.eventos_subsidio_raw"
eventos_pd = None
if not tabla_vacia_o_ausente(T_EVENTOS):
    eventos_pd = spark.table(T_EVENTOS).select("fecha_inicio", "fecha_fin").toPandas()
else:
    print(f"⚠️ {T_EVENTOS} no existe o está vacía: subsidio_activo queda nulo.")

features_pd = features.construir_features(variacion_pd, wti_pd, eventos_pd)
variacion_semanal = a_spark(variacion_pd, ESQ_VARIACION)
features_modelo = a_spark(features_pd, ESQ_FEATURES)
print(f"variacion_semanal: {len(variacion_pd)} filas | features_modelo: {len(features_pd)} filas")

# COMMAND ----------

# MAGIC %md ### 1.4 Escritura (tablas externas en `<ruta_equipo_oro>/gold/<tabla>/`, `overwrite`) y `COMMENT`s

# COMMAND ----------

COMENTARIOS_PRECIO_SEMANAL = {
    "semana_inicio": "Martes con el que empieza la semana. Las semanas van de martes a lunes, igual que los precios de referencia del MEM.",
    "semana_fin": "Lunes con el que termina la semana (semana_inicio + 6 días).",
    "combustible": "super, regular o diesel.",
    "precio_promedio": "Promedio de los precios de la semana en Q por galón, redondeado a 2 decimales. Si fuente es mem, es el precio de referencia semanal del MEM (Ciudad de Guatemala, autoservicio); si es fotos, el promedio de las lecturas de silver.precios.",
    "precio_min": "Precio mínimo de la semana en Q por galón.",
    "precio_max": "Precio máximo de la semana en Q por galón.",
    "n_registros": "Cantidad de precios que entraron en el promedio de la semana (1 por semana en el MEM; lecturas aceptadas en las fotos).",
    "fuente": "Origen del dato: fotos (silver.precios) o mem (silver.mem_referencia). Son filas separadas.",
}
COMENTARIOS_VARIACION = {
    "semana_inicio": "Martes con el que empieza la semana (martes a lunes).",
    "combustible": "super, regular o diesel.",
    "precio_promedio": "Precio promedio de la semana en Q por galón (serie del MEM).",
    "precio_anterior": "Precio promedio de la semana inmediatamente anterior. Nulo si esa semana no existe: las semanas faltantes no se rellenan ni se interpolan.",
    "dif_q": "precio_promedio - precio_anterior en Q por galón (2 decimales). Nulo si falta la semana anterior.",
    "dif_pct": "Variación porcentual contra la semana anterior: 100 * dif_q / precio_anterior (2 decimales). Nulo si falta la semana anterior.",
    "direccion": "sube si dif_q > umbral_q, baja si dif_q < -umbral_q y se_mantiene en cualquier otro caso. Nulo si dif_q es nulo.",
    "umbral_q": "Umbral en Q por galón usado para clasificar la dirección (widget umbral_q, 0.10 por defecto).",
}
COMENTARIOS_FEATURES = {
    "semana_inicio": "Martes con el que empieza la semana (martes a lunes).",
    "combustible": "super, regular o diesel.",
    "var_q_1": "Variación en Q por galón de la semana actual contra la anterior (dif_q de la semana). Nula si falta la semana anterior.",
    "var_q_2": "Variación (dif_q) de la semana previa a la actual. Nula si falta alguna de las semanas necesarias.",
    "var_q_3": "Variación (dif_q) de hace 2 semanas. Nula si falta alguna de las semanas necesarias.",
    "var_q_4": "Variación (dif_q) de hace 3 semanas. Nula si falta alguna de las semanas necesarias; queda nula durante las 4 semanas posteriores a un hueco.",
    "prom_movil_4": "Promedio del precio de las últimas 4 semanas consecutivas (incluida la actual) en Q por galón. Nulo si falta alguna de las 4 semanas.",
    "dif_super_diesel": "Precio de super menos precio de diesel de la misma semana, en Q por galón. Nulo si falta alguno de los dos.",
    "direccion_actual": "Dirección de la semana actual (sube, baja o se_mantiene) según variación_semanal. Nula si falta la semana anterior.",
    "wti_var_1": "Cambio del promedio semanal del petróleo WTI (FRED, USD por barril) contra la semana anterior. Nulo si falta el promedio de alguna de las dos semanas o no hay datos de FRED.",
    "subsidio_activo": "1 = hay un subsidio o apoyo con fechas confirmadas que cubre la semana (o la semana contiene su inicio confirmado); 0 = la semana es anterior al primer inicio confirmado; nulo = sin fecha confirmada (por ejemplo, el fin del Decreto 11-2026 no está confirmado, así que las semanas posteriores a su inicio quedan nulas salvo que otro evento con fechas completas las cubra). Las fechas vacias no se inventan.",
    "direccion_siguiente": "Objetivo del modelo: dirección de la semana siguiente (sube, baja o se_mantiene). Nulo en la última semana y cuando la semana siguiente no existe.",
}

guardar_oro(
    precio_semanal, "precio_semanal",
    "Precio semanal de combustibles en Q por galón (semana de martes a lunes) con promedio, mínimo, máximo y número de registros. Filas separadas para fotos (silver.precios) y mem (precios de referencia del MEM).",
    COMENTARIOS_PRECIO_SEMANAL)
guardar_oro(
    variacion_semanal, "variacion_semanal",
    "Variación del precio contra la semana inmediatamente anterior y direccion (sube, baja, se_mantiene) según umbral_q. Serie del MEM; las semanas faltantes no se rellenan.",
    COMENTARIOS_VARIACION)
guardar_oro(
    features_modelo, "features_modelo",
    "Variables del modelo de clasificación (variaciónes de las últimas semanas, promedio móvil, diferencia super-diésel, WTI y subsidio) y objetivo direccion_siguiente. Serie del MEM; nada se interpola: lo que depende de una semana faltante es nulo.",
    COMENTARIOS_FEATURES)

# COMMAND ----------

# MAGIC %md ### 1.5 Verificación y resumen
# MAGIC Una segunda corrida con los mismos datos de Plata y Bronce deja **exactamente los mismos conteos**
# MAGIC (las tablas se escriben con `overwrite`).

# COMMAND ----------

T = {n: spark.table(f"{GOLD}.{n}") for n in ("precio_semanal", "variacion_semanal", "features_modelo")}

# 1) Todas las semanas son martes (dayofweek de Spark: 3) y semana_fin es el lunes siguiente
assert T["precio_semanal"].filter("dayofweek(semana_inicio) <> 3 OR dayofweek(semana_fin) <> 2").count() == 0
for n in ("variacion_semanal", "features_modelo"):
    assert T[n].filter("dayofweek(semana_inicio) <> 3").count() == 0, f"{n}: semana_inicio no es martes"
# 2) Una fila por llave
assert T["precio_semanal"].groupBy("semana_inicio", "combustible", "fuente").count().filter("count > 1").count() == 0
for n in ("variacion_semanal", "features_modelo"):
    assert T[n].groupBy("semana_inicio", "combustible").count().filter("count > 1").count() == 0
# 3) La dirección sale de dif_q y del umbral; sin semana anterior no hay variación
v = T["variacion_semanal"]
assert v.filter("dif_q IS NULL AND direccion IS NOT NULL").count() == 0
assert v.filter(f"dif_q > {UMBRAL_Q} AND direccion <> 'sube'").count() == 0
assert v.filter(f"dif_q < -{UMBRAL_Q} AND direccion <> 'baja'").count() == 0
assert v.filter(f"abs(dif_q) <= {UMBRAL_Q} AND direccion <> 'se_mantiene'").count() == 0
# 4) Nada se interpola: la variación solo existe si la semana anterior está en la tabla
sin_previa = (v.alias("a").join(v.alias("b"),
              (F.col("a.combustible") == F.col("b.combustible"))
              & (F.col("b.semana_inicio") == F.date_sub(F.col("a.semana_inicio"), 7)), "left_anti"))
assert sin_previa.filter("dif_q IS NOT NULL").count() == 0, "hay variaciones contra semanas ausentes"

print("=" * 60)
print("RESUMEN DE ORO (parte de Datos)")
print("=" * 60)
for fuente, n in sorted((r["fuente"], r["count"]) for r in T["precio_semanal"].groupBy("fuente").count().collect()):
    print(f"precio_semanal [{fuente:<5}] : {n} filas")
print(f"variacion_semanal      : {v.count()} filas ({v.filter('dif_q IS NOT NULL').count()} con variación)")
for r in v.groupBy("direccion").count().orderBy("direccion").collect():
    print(f"   direccion = {r['direccion']}: {r['count']}")
ft = T["features_modelo"]
print(f"features_modelo        : {ft.count()} filas")
for c in ("var_q_1", "var_q_4", "prom_movil_4", "wti_var_1", "subsidio_activo", "direccion_siguiente"):
    print(f"   {c:<20} no nulos: {ft.filter(F.col(c).isNotNull()).count()}")
print("✅ Oro OK (segunda corrida: mismos conteos)")

# COMMAND ----------

display(ft.orderBy(F.col("semana_inicio").desc(), "combustible").limit(30))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Modelo y predicción (Modelos)
# MAGIC TODO (guía de Modelos, 5.1): línea base vs. regresión logística y árbol de decisión con
# MAGIC validación temporal en MLflow; escribir `predicciones` y `metricas_modelo`.
