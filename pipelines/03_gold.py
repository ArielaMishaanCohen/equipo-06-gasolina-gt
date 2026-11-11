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
dbutils.widgets.text("esquema_silver", "equipo6_silver")
dbutils.widgets.text("esquema_gold", "equipo6_gold")
dbutils.widgets.text("ruta_gold", "s3://cc3105-au-869227452861-us-east-2-an/equipo6/gold")
dbutils.widgets.text("umbral_q", "0.10")

CATALOGO = dbutils.widgets.get("catalogo")
SILVER = f"{CATALOGO}.{dbutils.widgets.get('esquema_silver')}"
GOLD = f"{CATALOGO}.{dbutils.widgets.get('esquema_gold')}"
RUTA_GOLD = dbutils.widgets.get("ruta_gold").rstrip("/")
UMBRAL_Q = float(dbutils.widgets.get("umbral_q"))


def guardar_oro(df, tabla: str, comentario: str):
    """Escribe una tabla Oro externa en RUTA_GOLD/<tabla> (overwrite = idempotente)."""
    (df.write.format("delta").mode("overwrite").option("overwriteSchema", "true")
       .option("path", f"{RUTA_GOLD}/{tabla}").saveAsTable(f"{GOLD}.{tabla}"))
    spark.sql(f"COMMENT ON TABLE {GOLD}.{tabla} IS '{comentario}'")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Indicadores y variables (Datos)
# MAGIC TODO (guía de Datos, 5.1): `precio_semanal` (semana martes a lunes), `variacion_semanal`
# MAGIC (dirección con `UMBRAL_Q`) y `features_modelo`, con `COMMENT` en cada columna.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Modelo y predicción (Modelos)
# MAGIC TODO (guía de Modelos, 5.1): línea base vs. regresión logística y árbol de decisión con
# MAGIC validación temporal en MLflow; escribir `predicciones` y `metricas_modelo`.
