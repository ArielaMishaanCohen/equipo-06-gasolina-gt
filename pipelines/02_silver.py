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
# MAGIC TODO (guía de Datos, 4.1–4.2):
# MAGIC - `gasolina.calidad.aplicar_reglas` → válidos y rechazados (`regla`, `motivo`).
# MAGIC - `MERGE INTO silver.precios` por `fecha + ubicacion + combustible + modalidad`.
# MAGIC - Rechazados → `silver.precios_rejected`.
# MAGIC - Resumen: fotos procesadas, filas válidas, rechazadas por regla, exactitud de la revisión manual.
