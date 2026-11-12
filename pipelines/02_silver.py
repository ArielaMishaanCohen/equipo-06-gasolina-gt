# Databricks notebook source
# MAGIC %md
# MAGIC # 02_silver — Extracción de precios y reglas de calidad (Fase 2)
# MAGIC
# MAGIC **ESQUELETO.** Partes: (1) extracción con OCR — **Modelos**; (2) reglas de calidad, cuarentena
# MAGIC y MERGE — **Datos**. Contratos 5.2 y 5.3 de `docs/instructivos/INSTRUCTIVO_GENERAL.md`.
# MAGIC Las guías de cada rol traen el prompt para implementarlo.

# COMMAND ----------

# MAGIC %pip install /Workspace/Users/TU_CORREO/gasolina-mlops

# COMMAND ----------

dbutils.library.restartPython()

# COMMAND ----------

dbutils.widgets.text("catalogo", "workspace")
dbutils.widgets.text("esquema_bronze", "equipo6_bronze")
dbutils.widgets.text("esquema_silver", "equipo6_silver")
dbutils.widgets.text("motor", "rapidocr")
dbutils.widgets.text("preproc", "gris_clahe")

CATALOGO = dbutils.widgets.get("catalogo")
BRONZE = f"{CATALOGO}.{dbutils.widgets.get('esquema_bronze')}"
SILVER = f"{CATALOGO}.{dbutils.widgets.get('esquema_silver')}"
MOTOR = dbutils.widgets.get("motor")
PREPROC = dbutils.widgets.get("preproc")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Extracción (Modelos)
# MAGIC TODO (guía de Modelos, 4.3):
# MAGIC - Leer de `bronze.fotos_precios` solo las fotos no procesadas con la `version_modelo` actual.
# MAGIC - Aplicar `gasolina.extraccion.extraer_precios` a `content` (pandas UDF / mapInPandas).
# MAGIC - Explotar `registros` a una fila por combustible → DataFrame `candidatos` (columnas de 5.3).
# MAGIC - Fotos sin registros → cuarentena con `motivo = "sin_precios_legibles"`.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Calidad, cuarentena y MERGE (Datos)
# MAGIC
# MAGIC Esta parte es de **Datos** y solo necesita que la parte 1 (Modelos) deje un DataFrame de Spark
# MAGIC llamado `candidatos` con **una fila por lectura de precio** y las columnas del contrato 5.3:
# MAGIC `fecha`, `combustible`, `precio_q_galon`, `modalidad`, `ubicacion`, `foto_origen`, `confianza`,
# MAGIC `motor`, `version_modelo`. Una foto sin ningún precio legible entra como **una fila con
# MAGIC `combustible` y `precio_q_galon` nulos** (se rechaza como `sin_precios_legibles`).
# MAGIC `_procesado_en` lo agrega este bloque. Si `candidatos` no existe todavía (la extracción aún no
# MAGIC está), se usa uno vacío: el notebook corre igual y solo refresca `silver.mem_referencia`.
# MAGIC
# MAGIC Qué hace: (1) aplica `gasolina.calidad` (5 reglas) → válidos y rechazados; (2) `MERGE` de los
# MAGIC válidos en `silver.precios` por `fecha + ubicacion + combustible + modalidad`;
# MAGIC (3) rechazados a `silver.precios_rejected` con `regla` y `motivo`; (4) histórico del MEM desde
# MAGIC Bronce a `silver.mem_referencia`; (5) resumen y comprobación de idempotencia.

# COMMAND ----------

dbutils.widgets.text("ruta_equipo_silver", "s3://cc3105-ag-869227452861-us-east-2-an/equipo6")
RUTA_SILVER = dbutils.widgets.get("ruta_equipo_silver").rstrip("/")

T_PRECIOS = f"{SILVER}.precios"
T_RECHAZADOS = f"{SILVER}.precios_rejected"
T_MEM = f"{SILVER}.mem_referencia"
T_MEM_RAW = f"{BRONZE}.mem_referencia_raw"

for t in (T_PRECIOS, T_RECHAZADOS):
    if not spark.catalog.tableExists(t):
        raise RuntimeError(f"No existe {t}. Corre primero pipelines/00_setup.sql.")

# COMMAND ----------

from pyspark.sql import Window
from pyspark.sql import functions as F
from pyspark.sql.types import DateType, DoubleType, StringType, StructField, StructType

from gasolina import calidad
from gasolina.config import cargar_config

ESQUEMA_CANDIDATOS = StructType([
    StructField("fecha", DateType()), StructField("combustible", StringType()),
    StructField("precio_q_galon", DoubleType()), StructField("modalidad", StringType()),
    StructField("ubicacion", StringType()), StructField("foto_origen", StringType()),
    StructField("confianza", DoubleType()), StructField("motor", StringType()),
    StructField("version_modelo", StringType()),
])
# Orden de columnas de silver.precios (contrato 5.3) y de silver.precios_rejected (+ regla, motivo)
COLS_PRECIOS = ["fecha", "combustible", "precio_q_galon", "modalidad", "ubicacion", "foto_origen",
                "confianza", "motor", "version_modelo", "_procesado_en"]
COLS_RECHAZADOS = COLS_PRECIOS + ["regla", "motivo"]
LLAVE = ["fecha", "ubicacion", "combustible", "modalidad"]

try:
    candidatos  # lo deja la parte 1 (Modelos)
except NameError:
    print("⚠️ No hay `candidatos` (la extracción aún no está): se usa un DataFrame vacío.")
    candidatos = spark.createDataFrame([], ESQUEMA_CANDIDATOS)

# Tipos del contrato; el sello de procesamiento se agrega aquí
candidatos_t = (
    candidatos.select(
        # try_cast: un valor mal formado queda NULL (y lo rechaza una regla) en vez de truenar (ANSI)
        F.expr("try_cast(fecha as date)").alias("fecha"), "combustible",
        F.expr("try_cast(precio_q_galon as double)").alias("precio_q_galon"), "modalidad",
        "ubicacion", "foto_origen", F.expr("try_cast(confianza as double)").alias("confianza"),
        "motor", "version_modelo")
    .withColumn("_procesado_en", F.current_timestamp())
    .cache()
)
fotos_procesadas = candidatos_t.select("foto_origen").distinct().count()
n_candidatos = candidatos_t.count()
print(f"Fotos procesadas: {fotos_procesadas} | lecturas candidatas: {n_candidatos}")

# COMMAND ----------

# MAGIC %md ### 2.1 Reglas de calidad (`gasolina.calidad`, versión Spark)

# COMMAND ----------

validos, rechazados = calidad.aplicar_reglas_spark(candidatos_t)  # hoy, rango y confianza: config.yaml
validos, rechazados = validos.cache(), rechazados.cache()
n_validos, n_rechazados = validos.count(), rechazados.count()
print(f"Válidos: {n_validos} | rechazados: {n_rechazados}")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 2.2 `MERGE` en `silver.precios` y cuarentena en `silver.precios_rejected`
# MAGIC
# MAGIC - Llave: `fecha + ubicacion + combustible + modalidad` (`modalidad` y `ubicacion` ya vienen con
# MAGIC   `no_indica`, nunca `null`). Si en una misma corrida hay varias lecturas de la misma llave, se
# MAGIC   conserva la de mayor confianza (el `MERGE` falla con duplicados en el origen).
# MAGIC - `precios_rejected` no tiene llave natural: antes de insertar se borran las filas de las fotos de
# MAGIC   esta corrida, así reprocesar la misma foto no duplica la cuarentena.

# COMMAND ----------

mejor_por_llave = Window.partitionBy(*LLAVE).orderBy(F.col("confianza").desc(), F.col("foto_origen").asc())
validos_unicos = (
    validos.withColumn("_n", F.row_number().over(mejor_por_llave)).filter("_n = 1").drop("_n")
    .select(
        "fecha", "combustible", F.expr("try_cast(precio_q_galon as decimal(6,2))").alias("precio_q_galon"),
        "modalidad", "ubicacion", "foto_origen", "confianza", "motor", "version_modelo", "_procesado_en")
    .cache()
)
n_duplicados_corrida = n_validos - validos_unicos.count()
validos_unicos.createOrReplaceTempView("validos_a_cargar")

rechazados_a_cargar = (
    rechazados.select(
        "fecha", "combustible", F.expr("try_cast(precio_q_galon as decimal(6,2))").alias("precio_q_galon"),
        "modalidad", "ubicacion", "foto_origen", "confianza", "motor", "version_modelo",
        "_procesado_en", "regla", "motivo")
    .cache()
)
candidatos_t.select("foto_origen").distinct().createOrReplaceTempView("fotos_de_la_corrida")


def cargar_precios():
    spark.sql(f"""
        MERGE INTO {T_PRECIOS} t USING validos_a_cargar s
        ON  t.fecha = s.fecha AND t.ubicacion = s.ubicacion
        AND t.combustible = s.combustible AND t.modalidad = s.modalidad
        WHEN MATCHED THEN UPDATE SET *
        WHEN NOT MATCHED THEN INSERT *
    """)


def cargar_rechazados():
    spark.sql(f"""
        DELETE FROM {T_RECHAZADOS}
        WHERE foto_origen IN (SELECT foto_origen FROM fotos_de_la_corrida)
    """)
    rechazados_a_cargar.select(*COLS_RECHAZADOS).write.mode("append").insertInto(T_RECHAZADOS)


cargar_precios()
cargar_rechazados()
print("Plata cargada: silver.precios =", spark.table(T_PRECIOS).count(),
      "| silver.precios_rejected =", spark.table(T_RECHAZADOS).count())

# COMMAND ----------

# MAGIC %md ### 2.3 Histórico del MEM → `silver.mem_referencia`
# MAGIC
# MAGIC Desde `bronze.mem_referencia_raw` (todo STRING): se normalizan combustible y modalidad, se tipa
# MAGIC y las fechas se llevan a la **semana de martes a lunes** (fórmula del contrato 5.4:
# MAGIC `fecha - ((dayofweek(fecha) - 3 + 7) % 7)`). Las filas sin precio, con combustible fuera del
# MAGIC catálogo o con precio fuera del rango de `config.yaml` se descartan y se cuentan; **las semanas
# MAGIC faltantes no se rellenan**. Si una semana trae varias filas iguales, se promedian.

# COMMAND ----------

cfg = cargar_config()
RMIN, RMAX = cfg["calidad"]["rango_precio"]["min"], cfg["calidad"]["rango_precio"]["max"]
CATALOGO_COMB = cfg["combustibles"]

spark.sql(f"""
    CREATE TABLE IF NOT EXISTS {T_MEM} (
      semana_inicio  DATE          COMMENT 'Martes con el que empieza la semana (martes a lunes, como el MEM)',
      semana_fin     DATE          COMMENT 'Lunes con el que termina la semana',
      combustible    STRING        COMMENT 'super, regular o diesel',
      modalidad      STRING        COMMENT 'autoservicio, servicio_completo o no_indica',
      region         STRING        COMMENT 'Región del precio de referencia (Ciudad de Guatemala)',
      precio_q_galon DECIMAL(6,2)  COMMENT 'Precio promedio de referencia del MEM en Q por galón',
      fuente_url     STRING        COMMENT 'Informe(s) del MEM de donde sale el dato',
      _procesado_en  TIMESTAMP     COMMENT 'Fecha y hora de la carga a Plata'
    )
    USING DELTA
    LOCATION '{RUTA_SILVER}/silver/mem_referencia'
    COMMENT 'Histórico semanal de precios de referencia del MEM, limpio y tipado. Semanas faltantes sin rellenar.'
""")

mem_resumen = {}
if not spark.catalog.tableExists(T_MEM_RAW) or spark.table(T_MEM_RAW).count() == 0:
    print(f"⚠️ {T_MEM_RAW} no existe o está vacía: silver.mem_referencia no se actualiza "
          "(sube el CSV del MEM y corre 01_bronze).")
else:
    raw = spark.table(T_MEM_RAW)


    def sin_acento(c):
        return F.translate(F.lower(F.trim(c)), "áéíóúü", "aeiouu")


    comb_txt = sin_acento(F.col("combustible"))
    limpio = raw.select(
        F.try_to_timestamp(F.trim(F.col("semana_inicio")), F.lit("yyyy-MM-dd")).cast("date")
         .alias("fecha_dato"),
        F.when(comb_txt.isin("superior", "gasolina superior", "gasolina super"), "super")
         .when(comb_txt == "gasolina regular", "regular")
         .when(comb_txt == "combustible diesel", "diesel")
         .otherwise(comb_txt).alias("combustible"),
        F.coalesce(F.when(F.trim("modalidad") == "", None).otherwise(sin_acento(F.col("modalidad"))),
                   F.lit("no_indica")).alias("modalidad"),
        F.trim("region").alias("region"),
        F.expr("try_cast(regexp_replace(trim(precio_q_galon), '^Q', '') as decimal(6,2))")
         .alias("precio"),
        F.trim("fuente_url").alias("fuente_url"),
    )
    n_raw = limpio.count()
    descartes = (
        limpio.withColumn("motivo",
            F.when(F.col("fecha_dato").isNull(), "fecha ausente o inválida")
             .when(F.col("precio").isNull(), "precio ausente")
             .when(~F.col("combustible").isin(*CATALOGO_COMB), "combustible fuera del catálogo")
             .when((F.col("precio") < RMIN) | (F.col("precio") > RMAX), "precio fuera de rango"))
        .filter("motivo IS NOT NULL").groupBy("motivo").count()
    )
    mem_resumen["descartes"] = {r["motivo"]: r["count"] for r in descartes.collect()}
    buenos = limpio.filter(
        F.col("fecha_dato").isNotNull() & F.col("precio").isNotNull()
        & F.col("combustible").isin(*CATALOGO_COMB) & F.col("precio").between(RMIN, RMAX))
    # Semana martes-lunes (dayofweek: 1 = domingo, 3 = martes)
    semanal = (
        buenos.withColumn("semana_inicio",
                          F.date_sub("fecha_dato", (F.dayofweek("fecha_dato") - 3 + 7) % 7))
        .groupBy("semana_inicio", "combustible", "modalidad", "region")
        .agg(F.round(F.avg("precio"), 2).cast("decimal(6,2)").alias("precio_q_galon"),
             F.concat_ws(" | ", F.sort_array(F.collect_set("fuente_url"))).alias("fuente_url"))
        .withColumn("semana_fin", F.date_add("semana_inicio", 6))
        .withColumn("_procesado_en", F.current_timestamp())
        .select("semana_inicio", "semana_fin", "combustible", "modalidad", "region",
                "precio_q_galon", "fuente_url", "_procesado_en")
    )
    # Recarga completa desde Bronce: idempotente (mismo CSV -> mismas filas)
    semanal.write.mode("overwrite").insertInto(T_MEM)
    mem_resumen.update(filas_raw=n_raw, filas_silver=spark.table(T_MEM).count())

# COMMAND ----------

# MAGIC %md ### 2.4 Resumen y comprobación de idempotencia
# MAGIC
# MAGIC Se vuelve a ejecutar la carga de Plata con los mismos datos: los conteos tienen que ser idénticos
# MAGIC (el `MERGE` actualiza y la cuarentena reemplaza, no duplica). Una segunda corrida de todo el
# MAGIC notebook también deja los mismos conteos.

# COMMAND ----------

conteo_1 = (spark.table(T_PRECIOS).count(), spark.table(T_RECHAZADOS).count())
cargar_precios()
cargar_rechazados()
conteo_2 = (spark.table(T_PRECIOS).count(), spark.table(T_RECHAZADOS).count())
assert conteo_1 == conteo_2, f"La carga no es idempotente: {conteo_1} vs {conteo_2}"

por_regla = {r["regla"]: r["count"] for r in rechazados.groupBy("regla").count().collect()}
print("=" * 60)
print("RESUMEN DE PLATA")
print("=" * 60)
print(f"Fotos procesadas en esta corrida : {fotos_procesadas}")
print(f"Lecturas candidatas              : {n_candidatos}")
print(f"Filas válidas                    : {n_validos}"
      + (f"  (cargadas {n_validos - n_duplicados_corrida}; {n_duplicados_corrida} duplicadas "
         "en la corrida, se conserva la de mayor confianza)" if n_duplicados_corrida else ""))
print(f"Filas rechazadas                 : {n_rechazados}")
for regla in calidad.TODAS_LAS_REGLAS:
    print(f"   {regla:<26}: {por_regla.get(regla, 0)}")
print(f"silver.precios                   : {conteo_2[0]} filas")
print(f"silver.precios_rejected          : {conteo_2[1]} filas")
if mem_resumen:
    print(f"MEM: {mem_resumen['filas_raw']} filas en Bronce -> {mem_resumen['filas_silver']} "
          f"semanas-combustible en silver.mem_referencia; descartes: {mem_resumen['descartes'] or 'ninguno'}")
print("✅ Segunda carga con los mismos datos: mismos conteos (idempotente)")

# COMMAND ----------

display(spark.table(T_RECHAZADOS).orderBy(F.col("_procesado_en").desc()).limit(50))
