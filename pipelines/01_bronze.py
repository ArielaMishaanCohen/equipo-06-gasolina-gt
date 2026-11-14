# Databricks notebook source
# MAGIC %md
# MAGIC # 01_bronze — Ingesta incremental de fotos y fuentes complementarias (Fase 1)
# MAGIC
# MAGIC 1. Lee las fotos de `ruta_fotos` (por defecto el Volume `crudos/fotos/`) con **Auto Loader**
# MAGIC    (`cloudFiles.format = binaryFile`, `trigger(availableNow=True)`) y las agrega a
# MAGIC    `bronze.fotos_precios` (contrato 5.1) con `_ingestion_timestamp`, `_source_file` y
# MAGIC    `fecha_carpeta`. El checkpoint recuerda qué archivos ya se cargaron: **una segunda corrida no
# MAGIC    duplica**.
# MAGIC 2. Carga las fuentes complementarias (histórico del MEM, eventos del subsidio y WTI de FRED)
# MAGIC    tal cual (todo STRING) a tablas `*_raw`, con las mismas columnas de auditoría.
# MAGIC 3. Verifica: filas en la tabla = fotos en la carpeta y cero `path` duplicados.
# MAGIC
# MAGIC Prerrequisito: haber corrido `00_setup.sql`. Todo lo que cambia llega como widget
# MAGIC (parámetros del Job). Si Auto Loader no está disponible, `modo = batch_merge` usa
# MAGIC `binaryFile` + `MERGE` por `path`.

# COMMAND ----------

dbutils.widgets.text("catalogo", "workspace")
dbutils.widgets.text("esquema_bronze", "equipo6_bronze")
dbutils.widgets.text("ruta_fotos", "/Volumes/workspace/equipo6_bronze/crudos/fotos/")
dbutils.widgets.text("ruta_equipo_bronze", "/Volumes/workspace/equipo6_bronze/crudos")
dbutils.widgets.text("ruta_repo", "")  # carpeta del Git folder (solo informativo / %pip install)
dbutils.widgets.dropdown("modo", "autoloader", ["autoloader", "batch_merge"])

CATALOGO = dbutils.widgets.get("catalogo")
ESQUEMA = dbutils.widgets.get("esquema_bronze")
RUTA_FOTOS = dbutils.widgets.get("ruta_fotos")
RUTA_EQUIPO = dbutils.widgets.get("ruta_equipo_bronze").rstrip("/")
RUTA_REPO = dbutils.widgets.get("ruta_repo")
MODO = dbutils.widgets.get("modo")
# Con s3:// las tablas *_raw son externas en esa ruta; con un Volume son gestionadas.
EXTERNAS = RUTA_EQUIPO.startswith("s3://")

TABLA = f"{CATALOGO}.{ESQUEMA}.fotos_precios"
CHECKPOINT = f"{RUTA_EQUIPO}/_checkpoints/fotos_precios/"
RUTA_COMPLEMENTARIAS = f"{RUTA_EQUIPO}/complementarias"
PATRON_FOTOS = "*.{jpg,jpeg,png,heic,JPG,JPEG,PNG,HEIC}"

print(f"Tabla: {TABLA}\nFotos: {RUTA_FOTOS}\nCheckpoint: {CHECKPOINT}\nModo: {MODO}")

# COMMAND ----------

# MAGIC %md ## 1. Fotos → `bronze.fotos_precios`

# COMMAND ----------

from pyspark.sql import functions as F

if not spark.catalog.tableExists(TABLA):
    raise RuntimeError(f"No existe {TABLA}. Corre primero pipelines/00_setup.sql.")


def con_auditoria(df):
    """Columnas del contrato 5.1. fecha_carpeta sale de .../AAAA-MM-DD/foto (NULL si no hay carpeta)."""
    fecha_txt = F.regexp_extract(F.col("path"), r"/(\d{4}-\d{2}-\d{2})/[^/]+$", 1)
    # try_to_timestamp: una carpeta con fecha imposible (2026-13-45) da NULL en vez de truenar (ANSI)
    fecha_carpeta = F.try_to_timestamp(F.when(fecha_txt != "", fecha_txt), F.lit("yyyy-MM-dd"))
    return (
        df.withColumn("fecha_carpeta", fecha_carpeta.cast("date"))
        .withColumn("_ingestion_timestamp", F.current_timestamp())
        .withColumn("_source_file", F.col("path"))
        .select("path", "modificationTime", "length", "content", "fecha_carpeta",
                "_ingestion_timestamp", "_source_file")
    )


filas_antes = spark.table(TABLA).count()

if MODO == "autoloader":
    flujo = (
        spark.readStream.format("cloudFiles")
        .option("cloudFiles.format", "binaryFile")
        .option("pathGlobFilter", PATRON_FOTOS)
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

filas_despues = spark.table(TABLA).count()
print(f"Filas antes: {filas_antes} | después: {filas_despues} | nuevas: {filas_despues - filas_antes}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Fuentes complementarias → tablas `*_raw`
# MAGIC
# MAGIC Se leen de `<ruta_equipo_bronze>/complementarias/` tal cual (todas las columnas como
# MAGIC STRING; la limpieza y el tipado son de Plata). Cada carga reemplaza la tabla completa
# MAGIC (archivos pequeños), así que también es idempotente. Si un archivo todavía no está,
# MAGIC se avisa y se sigue: **no se inventan datos**.
# MAGIC
# MAGIC | Archivo | Tabla |
# MAGIC | --- | --- |
# MAGIC | `mem/mem_referencia.csv` | `mem_referencia_raw` |
# MAGIC | `mem/eventos_subsidio.csv` | `eventos_subsidio_raw` |
# MAGIC | `fred/*.csv` (WTI) | `fred_raw` |

# COMMAND ----------

COMPLEMENTARIAS = [
    # (tabla, carpeta, patrón de archivo, descripción)
    ("mem_referencia_raw", "mem", "mem_referencia*.csv",
     "Histórico semanal de precios de referencia del MEM, tal cual (CSV)."),
    ("eventos_subsidio_raw", "mem", "eventos_subsidio*.csv",
     "Fechas de inicio y cambio del subsidio temporal, tal cual (CSV)."),
    ("fred_raw", "fred", "*.csv",
     "Serie de FRED (petróleo WTI, DCOILWTICO), tal cual (CSV)."),
]


def hay_archivos(carpeta, patron):
    try:
        archivos = dbutils.fs.ls(carpeta)
    except Exception as e:  # carpeta inexistente o sin permiso
        print(f"  ⚠️ No se pudo listar {carpeta}: {str(e).splitlines()[0]}")
        return False
    import fnmatch
    return any(fnmatch.fnmatch(a.name, patron) for a in archivos)


resumen_comp = []
for tabla, carpeta, patron, descripcion in COMPLEMENTARIAS:
    origen = f"{RUTA_COMPLEMENTARIAS}/{carpeta}/"
    destino = f"{CATALOGO}.{ESQUEMA}.{tabla}"
    print(f"→ {destino}  <-  {origen}{patron}")
    if not hay_archivos(origen, patron):
        print("  ⚠️ Sin archivos: se omite (subirlos y volver a correr).")
        resumen_comp.append((tabla, "omitida: sin archivos", None))
        continue
    df = (
        spark.read.format("csv")
        .option("header", "true")
        .option("inferSchema", "false")  # tal cual: todo STRING
        .option("pathGlobFilter", patron)
        .load(origen)
        .withColumn("_ingestion_timestamp", F.current_timestamp())
        .withColumn("_source_file", F.col("_metadata.file_path"))
    )
    (
        df.write.format("delta").mode("overwrite").option("overwriteSchema", "true")
        .options(**({"path": f"{RUTA_EQUIPO}/bronze/{tabla}"} if EXTERNAS else {}))
        .saveAsTable(destino)
    )
    spark.sql(f"COMMENT ON TABLE {destino} IS '{descripcion} Columnas de auditoría: _ingestion_timestamp, _source_file.'")
    n = spark.table(destino).count()
    resumen_comp.append((tabla, "cargada", n))
    print(f"  ✅ {n} filas")

# COMMAND ----------

# MAGIC %md ## 3. Criterio de aceptación: filas = fotos en la carpeta, sin duplicados

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
print("Complementarias:", *[f"{t}={e}{'' if n is None else f' ({n} filas)'}" for t, e, n in resumen_comp], sep="\n  ")

assert duplicados == 0, "Hay fotos duplicadas en Bronce"
assert filas == fotos_en_carpeta, (
    f"Filas ({filas}) no coincide con las fotos de la carpeta ({fotos_en_carpeta})"
)
print("✅ Bronce OK")

# COMMAND ----------

display(
    spark.table(TABLA)
    .select("path", "length", "modificationTime", "fecha_carpeta", "_ingestion_timestamp")
    .orderBy("path")
)
