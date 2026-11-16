-- Databricks notebook source
-- MAGIC %md
-- MAGIC # 00_setup — Esquemas y Volume de trabajo del equipo 06
-- MAGIC
-- MAGIC Se corre **una sola vez** (es idempotente: `IF NOT EXISTS`). Crea los 3 esquemas de la
-- MAGIC arquitectura medallón y el Volume de archivos de trabajo. Las **tablas** las crea cada notebook
-- MAGIC (`01_bronze`, `02_silver`, `03_gold`) si no existen, así que el Job también funciona desde cero.
-- MAGIC
-- MAGIC **Almacenamiento (16 nov):**
-- MAGIC
-- MAGIC | Qué | Dónde |
-- MAGIC | --- | --- |
-- MAGIC | Fotos del catedrático | `s3://cc3105-raw-…/img/`, leídas por la external location `xloc-raw` (solo lectura) |
-- MAGIC | Tablas Bronce / Plata / Oro | `workspace.equipo_06_bronze/silver/gold`. Gestionadas mientras `xloc-cusn/ag/au` sean de solo lectura; con `ruta_tablas_bronze`, `ruta_equipo_silver` y `ruta_equipo_oro` = `s3://…/equipo6` se crean como **externas** en el bucket de su capa |
-- MAGIC | Archivos de trabajo | Volume `workspace.equipo6_bronze.crudos` |
-- MAGIC
-- MAGIC | Carpeta del Volume | Contenido |
-- MAGIC | --- | --- |
-- MAGIC | `complementarias/mem/` | `mem_referencia.csv`, `eventos_subsidio.csv` |
-- MAGIC | `complementarias/fred/` | CSV de FRED (WTI) |
-- MAGIC | `etiquetas.csv` | Revisión manual de fotos (exactitud de la extracción) |
-- MAGIC | `_checkpoints/<esquema>/` | Lo escribe Auto Loader (no tocar) |
-- MAGIC | `_wheels/` | Paquete `gasolina` que instalan los notebooks |

-- COMMAND ----------

CREATE SCHEMA IF NOT EXISTS workspace.equipo_06_bronze COMMENT 'Equipo 06 - capa Bronce: fotos tal como llegan';
CREATE SCHEMA IF NOT EXISTS workspace.equipo_06_silver COMMENT 'Equipo 06 - capa Plata: precios limpios y cuarentena';
CREATE SCHEMA IF NOT EXISTS workspace.equipo_06_gold   COMMENT 'Equipo 06 - capa Oro: indicadores semanales, modelo y predicciones';

-- Volume de archivos de trabajo (vive en el esquema donde se creó al inicio del proyecto).
CREATE SCHEMA IF NOT EXISTS workspace.equipo6_bronze COMMENT 'Equipo 06 - Volume de archivos de trabajo';
CREATE VOLUME IF NOT EXISTS workspace.equipo6_bronze.crudos
COMMENT 'Equipo 06 - archivos de trabajo: complementarias/, etiquetas.csv, checkpoints de Auto Loader y wheels';

-- COMMAND ----------

-- MAGIC %md ## Permisos para el equipo y el catedrático

-- COMMAND ----------

GRANT ALL PRIVILEGES ON SCHEMA workspace.equipo_06_bronze TO `account users`;
GRANT ALL PRIVILEGES ON SCHEMA workspace.equipo_06_silver TO `account users`;
GRANT ALL PRIVILEGES ON SCHEMA workspace.equipo_06_gold   TO `account users`;

-- COMMAND ----------

-- MAGIC %md ## Comprobación: la carpeta de fotos se lee por la external location

-- COMMAND ----------

LIST 's3://cc3105-raw-869227452861-us-east-2-an/img/';
