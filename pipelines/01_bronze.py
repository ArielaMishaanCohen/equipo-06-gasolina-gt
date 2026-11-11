# Databricks notebook source
# MAGIC %md
# MAGIC # 01_bronze — Ingesta incremental de fotos (Fase 1)
# MAGIC
# MAGIC Lee las fotos del bucket **raw** (`xloc-raw`, solo lectura) con **Auto Loader**
# MAGIC (`cloudFiles.format = binaryFile`) y las agrega a `bronze.fotos_precios` con las columnas de
# MAGIC auditoría `_ingestion_timestamp` y `_source_file`. El checkpoint guarda qué archivos ya se
# MAGIC cargaron, así que una segunda corrida **no duplica** (criterio de aceptación).
# MAGIC
# MAGIC Todos los valores que cambian llegan como widgets (parámetros del Job).

# COMMAND ----------

dbutils.widgets.text("catalogo", "workspace")
dbutils.widgets.text("esquema_bronze", "equipo6_bronze")
dbutils.widgets.text("ruta_fotos", "s3://cc3105-raw-869227452861-us-east-2-an/img/")
dbutils.widgets.text("ruta_bronze", "s3://cc3105-cusn-869227452861-us-east-2-an/equipo6")
dbutils.widgets.dropdown("modo", "autoloader", ["autoloader", "batch_merge"])

CATALOGO = dbutils.widgets.get("catalogo")
ESQUEMA = dbutils.widgets.get("esquema_bronze")
RUTA_FOTOS = dbutils.widgets.get("ruta_fotos")
RUTA_BRONZE = dbutils.widgets.get("ruta_bronze").rstrip("/")
MODO = dbutils.widgets.get("modo")

TABLA = f"{CATALOGO}.{ESQUEMA}.fotos_precios"
CHECKPOINT = f"{RUTA_BRONZE}/_checkpoints/fotos_precios"
PATRON_FOTOS = "*.{HEIC,heic,HEIF,heif,JPG,jpg,JPEG,jpeg,PNG,png}"
print(TABLA, "<-", RUTA_FOTOS, "| modo:", MODO)

# COMMAND ----------

from pyspark.sql import functions as F


def con_auditoria(df):
    """Columnas de auditoría + fecha de la carpeta fotos/AAAA-MM-DD/ (NULL si no hay)."""
    fecha_txt = F.regexp_extract(F.col("path"), r"/(\d{4}-\d{2}-\d{2})/[^/]+$", 1)
    return (
        df.withColumn("fecha_carpeta", F.to_date(F.when(fecha_txt != "", fecha_txt)))
        .withColumn("_ingestion_timestamp", F.current_timestamp())
        .withColumn("_source_file", F.col("path"))
        .select("path", "modificationTime", "length", "content", "fecha_carpeta",
                "_ingestion_timestamp", "_source_file")
    )


antes = spark.table(TABLA).count()

if MODO == "autoloader":
    flujo = (
        spark.readStream.format("cloudFiles")
        .option("cloudFiles.format", "binaryFile")
        .option("pathGlobFilter", PATRON_FOTOS)
        .option("recursiveFileLookup", "true")
        .load(RUTA_FOTOS)
    )
    (
        con_auditoria(flujo)
        .writeStream.option("checkpointLocation", CHECKPOINT)
        .trigger(availableNow=True)
        .toTable(TABLA)
        .awaitTermination()
    )
else:
    # Alternativa sin Auto Loader: lectura batch + MERGE por path (también idempotente).
    nuevas = con_auditoria(
        spark.read.format("binaryFile")
        .option("pathGlobFilter", PATRON_FOTOS)
        .option("recursiveFileLookup", "true")
        .load(RUTA_FOTOS)
    )
    nuevas.createOrReplaceTempView("fotos_nuevas")
    spark.sql(f"""
        MERGE INTO {TABLA} t USING fotos_nuevas s ON t.path = s.path
        WHEN NOT MATCHED THEN INSERT *
    """)

despues = spark.table(TABLA).count()
print(f"Filas antes: {antes} | después: {despues} | nuevas: {despues - antes}")

# COMMAND ----------

# MAGIC %md ## Criterio de aceptación: filas = fotos en la carpeta, sin duplicados

# COMMAND ----------

fotos_en_carpeta = (
    spark.read.format("binaryFile").option("pathGlobFilter", PATRON_FOTOS)
    .option("recursiveFileLookup", "true").load(RUTA_FOTOS).select("path").count()
)
filas = spark.table(TABLA).count()
duplicados = spark.table(TABLA).groupBy("path").count().filter("count > 1").count()

print(f"Fotos en {RUTA_FOTOS}: {fotos_en_carpeta}")
print(f"Filas en {TABLA}: {filas}")
print(f"Paths duplicados: {duplicados}")
assert duplicados == 0, "Hay fotos duplicadas en Bronce"
assert filas == fotos_en_carpeta, "El número de filas no coincide con las fotos de la carpeta"
print("✅ Bronce OK")

# COMMAND ----------

display(
    spark.table(TABLA)
    .select("path", "length", "modificationTime", "fecha_carpeta", "_ingestion_timestamp")
    .orderBy("path")
)
