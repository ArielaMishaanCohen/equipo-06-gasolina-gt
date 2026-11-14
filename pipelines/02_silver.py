# Databricks notebook source
# MAGIC %md
# MAGIC # 02_silver — Extracción de precios y reglas de calidad (Fase 2)
# MAGIC
# MAGIC Partes: (1) extracción con OCR — **Modelos**; (2) reglas de calidad, cuarentena
# MAGIC y MERGE — **Datos**. Contratos 5.2 y 5.3 de `docs/instructivos/INSTRUCTIVO_GENERAL.md`.
# MAGIC Guía de ejecución: `docs/instructivos/PERSONA_1_DATABRICKS.md`.

# COMMAND ----------

# Instalar el paquete `gasolina` del repo. En un Job con git_source el repo está en una carpeta
# de solo lectura (pip no puede construir ahí): se copia a /tmp, se construye el wheel en el
# Volume del equipo (visible para driver y workers) y se instala ese wheel.
import glob
import os
import shutil
import subprocess
import sys

_src, _wheels = "/tmp/gasolina-src", "/Volumes/workspace/equipo6_bronze/crudos/_wheels"
shutil.rmtree(_src, ignore_errors=True)
shutil.copytree(os.path.abspath(".."), _src, ignore=shutil.ignore_patterns(
    ".git", ".venv", "tests", "docs", "presentacion", "artifacts_demo", "*.egg-info", "__pycache__"))
os.makedirs(_wheels, exist_ok=True)
for _w in glob.glob(f"{_wheels}/gasolina-*.whl"):
    os.remove(_w)
subprocess.run([sys.executable, "-m", "pip", "wheel", "--no-deps", "-q", "-w", _wheels, _src],
               check=True)
WHEEL_GASOLINA = sorted(glob.glob(f"{_wheels}/gasolina-*.whl"))[-1]
print(WHEEL_GASOLINA)

# COMMAND ----------

# MAGIC %pip install $WHEEL_GASOLINA

# COMMAND ----------

dbutils.library.restartPython()

# COMMAND ----------

dbutils.widgets.text("catalogo", "workspace")
dbutils.widgets.text("esquema_bronze", "equipo6_bronze")
dbutils.widgets.text("esquema_silver", "equipo6_silver")
dbutils.widgets.text("motor", "rapidocr")
dbutils.widgets.text("preproc", "gris_clahe")
dbutils.widgets.dropdown("reprocesar", "false", ["false", "true"])
dbutils.widgets.text("ruta_etiquetas", "")
dbutils.widgets.text("ruta_reporte_exactitud", "")

CATALOGO = dbutils.widgets.get("catalogo")
BRONZE = f"{CATALOGO}.{dbutils.widgets.get('esquema_bronze')}"
SILVER = f"{CATALOGO}.{dbutils.widgets.get('esquema_silver')}"
MOTOR = dbutils.widgets.get("motor")
PREPROC = dbutils.widgets.get("preproc")
REPROCESAR = dbutils.widgets.get("reprocesar") == "true"
RUTA_ETIQUETAS = dbutils.widgets.get("ruta_etiquetas").strip()
RUTA_REPORTE = dbutils.widgets.get("ruta_reporte_exactitud").strip().rstrip("/")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Extracción (Modelos)
# MAGIC Se leen los bytes de Bronce con `mapInPandas`. Se omiten fotos que ya figuran en precios
# MAGIC o cuarentena para el motor y versión actuales. Cambiar `preproc` requiere `reprocesar=true`
# MAGIC porque el contrato de Plata no almacena el preprocesamiento.
# MAGIC Las fotos sin registros se conservan como testigos nulos para la cuarentena de Datos.

# COMMAND ----------

import json
from functools import partial

import pandas as pd
from pyspark.sql import functions as F
from pyspark.sql.types import DateType, DoubleType, StringType, StructField, StructType

from gasolina import __version__
from gasolina.ocr import MOTORES, PREPROCS
from gasolina.silver_extraccion import (
    candidatos_lote,
    comprobar_dependencias,
    evaluar_resultados,
    extraer_lote,
)

if MOTOR not in MOTORES or PREPROC not in PREPROCS:
    raise ValueError(f"motor/preproc inválidos. Opciones: {MOTORES}, {PREPROCS}")

VERSION_MODELO = __version__
T_FOTOS = f"{BRONZE}.fotos_precios"
T_PRECIOS = f"{SILVER}.precios"
T_RECHAZADOS = f"{SILVER}.precios_rejected"
for tabla in (T_FOTOS, T_PRECIOS, T_RECHAZADOS):
    if not spark.catalog.tableExists(tabla):
        raise RuntimeError(f"No existe {tabla}. Ejecuta 00_setup y 01_bronze con Datos.")

# Prueba real de importación y del motor, primero en driver y luego en un worker.
dependencias_driver = comprobar_dependencias(MOTOR)


def verificar_worker(lotes):
    from gasolina.silver_extraccion import comprobar_dependencias

    for lote in lotes:
        if len(lote):
            yield pd.DataFrame([{"entorno": "worker", "versiones": json.dumps(
                comprobar_dependencias(MOTOR), ensure_ascii=False)}])


dependencias_worker = spark.range(1).mapInPandas(
    verificar_worker, "entorno string, versiones string").collect()
display(spark.createDataFrame(
    [("driver", json.dumps(dependencias_driver)),
     *[(r.entorno, r.versiones) for r in dependencias_worker]],
    "entorno string, versiones string"))

# COMMAND ----------

fotos_bronce = spark.table(T_FOTOS).select("path", "content", "fecha_carpeta")
procesadas = (
    spark.table(T_PRECIOS).select("foto_origen", "motor", "version_modelo")
    .unionByName(spark.table(T_RECHAZADOS).select("foto_origen", "motor", "version_modelo"))
    .filter((F.col("version_modelo") == VERSION_MODELO) & (F.col("motor") == MOTOR))
    .select(F.col("foto_origen").alias("path")).distinct()
)
pendientes = (fotos_bronce if REPROCESAR
              else fotos_bronce.join(procesadas, "path", "left_anti"))
print(f"Versión: {VERSION_MODELO} | motor: {MOTOR} | preproc: {PREPROC}")
print(f"Fotos pendientes: {pendientes.count()} | reprocesar: {REPROCESAR}")

# Limitar bytes por lote Arrow: las fotos HEIC pueden pesar varios MB.
# (En serverless esta configuración no se puede cambiar: se usa la de la plataforma.)
try:
    spark.conf.set("spark.sql.execution.arrow.maxRecordsPerBatch", "4")
except Exception as e:
    print(f"(arrow.maxRecordsPerBatch no configurable aquí: {str(e).splitlines()[0][:80]})")


def cachear(df):
    """cache() si el cómputo lo permite; en serverless no está disponible y no hace falta."""
    try:
        return df.cache()
    except Exception:
        return df


ESQUEMA_RESULTADOS = "foto_origen string, resultado_json string"
extraer_particion = partial(extraer_lote, motor=MOTOR, preproc=PREPROC,
                           version_modelo=VERSION_MODELO)
# El OCR se materializa en una tabla de la corrida (no basta con cache(): en serverless no existe
# y, sin materializar, "pendientes" se recalcularía vacío después del MERGE).
T_EXTRACCION = f"{SILVER}._extraccion_corrida"
(pendientes.mapInPandas(extraer_particion, ESQUEMA_RESULTADOS)
 .write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(T_EXTRACCION))
extraidas = spark.table(T_EXTRACCION)
print(f"Fotos extraídas: {extraidas.count()}")

ESQUEMA_CANDIDATOS = StructType([
    StructField("fecha", DateType()), StructField("combustible", StringType()),
    StructField("precio_q_galon", DoubleType()), StructField("modalidad", StringType()),
    StructField("ubicacion", StringType()), StructField("foto_origen", StringType()),
    StructField("confianza", DoubleType()), StructField("motor", StringType()),
    StructField("version_modelo", StringType()),
])
candidatos = cachear(extraidas.mapInPandas(candidatos_lote, ESQUEMA_CANDIDATOS))
print(f"Lecturas candidatas (incluye testigos sin precios): {candidatos.count()}")
display(candidatos)

# COMMAND ----------

# MAGIC %md
# MAGIC ### 1.1 Exactitud frente a revisión manual (sección 4.4)
# MAGIC
# MAGIC `ruta_etiquetas`: CSV de Persona 2 en S3 o un Volume, con `foto,combustible,precio_q_galon`.
# MAGIC Se evalúan todas las fotos etiquetadas, incluso las procesadas en corridas anteriores.
# MAGIC Se compara la extracción **antes** de calidad con tolerancia estricta `abs(pred-real) < 0.005`.
# MAGIC `sin_etiqueta` son lecturas adicionales sin verdad manual; no se cuentan como errores.
# MAGIC `ruta_reporte_exactitud` opcional: carpeta S3 o Volume para guardar resumen y detalle CSV.

# COMMAND ----------

if not RUTA_ETIQUETAS:
    display(spark.createDataFrame(
        [("pendiente", "Configura ruta_etiquetas con el CSV revisado por Persona 2")],
        "estado string, siguiente_paso string"))
else:
    etiquetas_df = spark.read.option("header", True).csv(RUTA_ETIQUETAS)
    requeridas = {"foto", "combustible", "precio_q_galon"}
    if not requeridas.issubset(etiquetas_df.columns):
        raise ValueError(f"Faltan columnas en etiquetas.csv: {requeridas - set(etiquetas_df.columns)}")
    etiquetas = [r.asDict() for r in etiquetas_df.collect()]
    nombres = sorted({r["foto"].replace("\\", "/").rsplit("/", 1)[-1] for r in etiquetas})
    fotos_revision = fotos_bronce.filter(F.element_at(F.split("path", "/"), -1).isin(nombres))
    # Reutilizar la extracción actual; solo ejecutar OCR de las etiquetadas faltantes.
    faltantes_revision = fotos_revision.join(
        extraidas.select(F.col("foto_origen").alias("path")), "path", "left_anti")
    resultados_revision = extraidas.unionByName(
        faltantes_revision.mapInPandas(extraer_particion, ESQUEMA_RESULTADOS))
    resumen_exactitud, detalle_exactitud = evaluar_resultados(
        (r.asDict() for r in resultados_revision.toLocalIterator()), etiquetas)
    contexto = {"motor": MOTOR, "preproc": PREPROC, "version_modelo": VERSION_MODELO}
    # Esquemas explícitos: también permiten evaluar si todas las fotos están ausentes
    # (en ese caso tiempo_ms es NULL para todas las filas).
    tabla_resumen = spark.createDataFrame([{**resumen_exactitud, **contexto}], """
        etiquetados long, correctos long, incorrectos long, no_encontrados long,
        sin_etiqueta long, pct_precios_correctos double, pct_fotos_completas double,
        tiempo_ms_promedio long, fotos_etiquetadas long, fotos_evaluadas long,
        fotos_ausentes long, motor string, preproc string, version_modelo string
    """)
    tabla_detalle = spark.createDataFrame(detalle_exactitud, """
        foto string, etiquetados long, correctos long, incorrectos long, no_encontrados long,
        sin_etiqueta long, pct_precios_correctos double, tiempo_ms long,
        foto_en_bronce boolean, detalle string
    """)
    display(tabla_resumen)
    display(tabla_detalle)
    if resumen_exactitud["fotos_evaluadas"] < 20:
        print("PENDIENTE: se necesitan al menos 20 fotos etiquetadas presentes en Bronce.")
    if resumen_exactitud["fotos_ausentes"]:
        print("PENDIENTE: hay fotos etiquetadas ausentes en Bronce; aparecen como no encontradas.")
    if RUTA_REPORTE:
        for nombre, tabla in (("resumen", tabla_resumen), ("por_foto", tabla_detalle)):
            (tabla.coalesce(1).write.mode("overwrite").option("header", True)
             .csv(f"{RUTA_REPORTE}/{nombre}"))
        print(f"Reporte guardado en {RUTA_REPORTE} (carpetas con part-*.csv).")

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

# Vacío = tabla gestionada (workspace propio). Con s3://… se crea como externa en esa ruta.
dbutils.widgets.text("ruta_equipo_silver", "")
RUTA_SILVER = dbutils.widgets.get("ruta_equipo_silver").strip().rstrip("/")
LOCATION_MEM = f"LOCATION '{RUTA_SILVER}/silver/mem_referencia'" if RUTA_SILVER else ""

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
)
candidatos_t = cachear(candidatos_t)
fotos_procesadas = candidatos_t.select("foto_origen").distinct().count()
n_candidatos = candidatos_t.count()
print(f"Fotos procesadas: {fotos_procesadas} | lecturas candidatas: {n_candidatos}")

# COMMAND ----------

# MAGIC %md ### 2.1 Reglas de calidad (`gasolina.calidad`, versión Spark)

# COMMAND ----------

validos, rechazados = calidad.aplicar_reglas_spark(candidatos_t)  # hoy, rango y confianza: config.yaml
validos, rechazados = cachear(validos), cachear(rechazados)
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
)
validos_unicos = cachear(validos_unicos)
n_duplicados_corrida = n_validos - validos_unicos.count()
validos_unicos.createOrReplaceTempView("validos_a_cargar")

rechazados_a_cargar = (
    rechazados.select(
        "fecha", "combustible", F.expr("try_cast(precio_q_galon as decimal(6,2))").alias("precio_q_galon"),
        "modalidad", "ubicacion", "foto_origen", "confianza", "motor", "version_modelo",
        "_procesado_en", "regla", "motivo")
)
rechazados_a_cargar = cachear(rechazados_a_cargar)
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
    {LOCATION_MEM}
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
