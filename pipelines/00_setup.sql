-- Databricks notebook source
-- MAGIC %md
-- MAGIC # 00_setup — Esquemas y tablas externas del equipo 6
-- MAGIC
-- MAGIC Se corre **una sola vez** (es idempotente: `IF NOT EXISTS`). Crea los 3 esquemas y las tablas
-- MAGIC Delta **externas** en el prefijo `equipo6/` de cada bucket (contratos 5.1, 5.3 y 5.4 de
-- MAGIC `docs/instructivos/INSTRUCTIVO_GENERAL.md`).
-- MAGIC
-- MAGIC | Capa | External location | Ruta |
-- MAGIC | --- | --- | --- |
-- MAGIC | Fotos (solo lectura) | `xloc-raw` | `s3://cc3105-raw-869227452861-us-east-2-an/img/` |
-- MAGIC | Bronce | `xloc-cusn` | `s3://cc3105-cusn-869227452861-us-east-2-an/equipo6/` |
-- MAGIC | Plata | `xloc-ag` | `s3://cc3105-ag-869227452861-us-east-2-an/equipo6/` |
-- MAGIC | Oro | `xloc-au` | `s3://cc3105-au-869227452861-us-east-2-an/equipo6/` |
-- MAGIC
-- MAGIC Si sale `User cannot write to a read-only external location`, el catedrático tiene que
-- MAGIC desmarcar *read only* en la external location. Si el catálogo o los esquemas cambian, se
-- MAGIC cambian aquí y en `config/config.yaml`.

-- COMMAND ----------

CREATE SCHEMA IF NOT EXISTS workspace.equipo6_bronze COMMENT 'Equipo 6 - capa Bronce: fotos tal como llegan';
CREATE SCHEMA IF NOT EXISTS workspace.equipo6_silver COMMENT 'Equipo 6 - capa Plata: precios limpios y cuarentena';
CREATE SCHEMA IF NOT EXISTS workspace.equipo6_gold   COMMENT 'Equipo 6 - capa Oro: indicadores semanales, modelo y predicciones';

-- COMMAND ----------

-- MAGIC %md ## Bronce

-- COMMAND ----------

CREATE TABLE IF NOT EXISTS workspace.equipo6_bronze.fotos_precios (
  path                 STRING    COMMENT 'Ruta completa de la foto en S3 (llave natural)',
  modificationTime     TIMESTAMP COMMENT 'Fecha de modificación del archivo en S3',
  length               BIGINT    COMMENT 'Tamaño en bytes',
  content              BINARY    COMMENT 'Contenido binario de la foto',
  fecha_carpeta        DATE      COMMENT 'Fecha de la carpeta fotos/AAAA-MM-DD/ si existe (si no, NULL: la fecha sale del EXIF en Plata)',
  _ingestion_timestamp TIMESTAMP COMMENT 'Fecha y hora de la carga a Bronce',
  _source_file         STRING    COMMENT 'Ruta de la foto de origen'
)
USING DELTA
LOCATION 's3://cc3105-cusn-869227452861-us-east-2-an/equipo6/bronze/fotos_precios'
COMMENT 'Fotos de precios tal como llegan del bucket raw, con columnas de auditoría. Carga incremental (Auto Loader).';

-- COMMAND ----------

-- MAGIC %md ## Plata

-- COMMAND ----------

CREATE TABLE IF NOT EXISTS workspace.equipo6_silver.precios (
  fecha           DATE          COMMENT 'Fecha de la foto (EXIF; si no hay, la de la carpeta)',
  combustible     STRING        COMMENT 'super, regular o diesel',
  precio_q_galon  DECIMAL(6,2)  COMMENT 'Precio en quetzales por galón',
  modalidad       STRING        COMMENT 'autoservicio, servicio_completo o no_indica',
  ubicacion       STRING        COMMENT 'Estación o municipio si aparece; si no, no_indica',
  foto_origen     STRING        COMMENT 'Ruta de la foto en Bronce',
  confianza       DOUBLE        COMMENT 'Confianza de la lectura (0 a 1)',
  motor           STRING        COMMENT 'Motor de OCR usado',
  version_modelo  STRING        COMMENT 'Versión del paquete gasolina que hizo la extracción',
  _procesado_en   TIMESTAMP     COMMENT 'Fecha y hora del procesamiento'
)
USING DELTA
LOCATION 's3://cc3105-ag-869227452861-us-east-2-an/equipo6/silver/precios'
COMMENT 'Un precio por fecha, ubicación, combustible y modalidad. Cargada con MERGE (idempotente).';

CREATE TABLE IF NOT EXISTS workspace.equipo6_silver.precios_rejected (
  fecha           DATE,
  combustible     STRING,
  precio_q_galon  DECIMAL(6,2),
  modalidad       STRING,
  ubicacion       STRING,
  foto_origen     STRING,
  confianza       DOUBLE,
  motor           STRING,
  version_modelo  STRING,
  _procesado_en   TIMESTAMP,
  regla           STRING COMMENT 'Regla de calidad que falló',
  motivo          STRING COMMENT 'Explicación del rechazo'
)
USING DELTA
LOCATION 's3://cc3105-ag-869227452861-us-east-2-an/equipo6/silver/precios_rejected'
COMMENT 'Cuarentena: lecturas que no pasaron las reglas de calidad, con el motivo.';

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ## Oro
-- MAGIC Las tablas Oro las crea `03_gold` con `overwrite` y `LOCATION` en
-- MAGIC `s3://cc3105-au-869227452861-us-east-2-an/equipo6/gold/<tabla>/` (la API lee esas rutas).

-- COMMAND ----------

SHOW TABLES IN workspace.equipo6_bronze;
