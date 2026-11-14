-- Databricks notebook source
-- MAGIC %md
-- MAGIC # 00_setup — Esquemas, Volume y tablas del equipo 6
-- MAGIC
-- MAGIC Se corre **una sola vez** (es idempotente: `IF NOT EXISTS`). Crea los 3 esquemas, el Volume
-- MAGIC de archivos crudos y las tablas Delta **gestionadas** de Bronce y Plata (contratos 5.1, 5.3 y
-- MAGIC 5.4 de `docs/instructivos/INSTRUCTIVO_GENERAL.md`).
-- MAGIC
-- MAGIC **Almacenamiento (decisión del 13 nov):** el catedrático indicó usar nuestro propio
-- MAGIC workspace. Las tablas son gestionadas por Unity Catalog (sin `LOCATION`) y los archivos
-- MAGIC (fotos y CSV) viven en el Volume `workspace.equipo6_bronze.crudos`:
-- MAGIC
-- MAGIC | Carpeta del Volume | Contenido |
-- MAGIC | --- | --- |
-- MAGIC | `fotos/` | Fotos de bombas (HEIC/JPG), opcionalmente en subcarpetas `AAAA-MM-DD/` |
-- MAGIC | `complementarias/mem/` | `mem_referencia.csv`, `eventos_subsidio.csv` |
-- MAGIC | `complementarias/fred/` | CSV de FRED (WTI) |
-- MAGIC | `_checkpoints/` | Lo escribe Auto Loader (no tocar) |
-- MAGIC
-- MAGIC Para volver a los buckets S3 del curso basta con pasar rutas `s3://…` en los widgets
-- MAGIC `ruta_*` de los notebooks: con `s3://` las tablas se escriben como externas.

-- COMMAND ----------

CREATE SCHEMA IF NOT EXISTS workspace.equipo6_bronze COMMENT 'Equipo 6 - capa Bronce: fotos tal como llegan';
CREATE SCHEMA IF NOT EXISTS workspace.equipo6_silver COMMENT 'Equipo 6 - capa Plata: precios limpios y cuarentena';
CREATE SCHEMA IF NOT EXISTS workspace.equipo6_gold   COMMENT 'Equipo 6 - capa Oro: indicadores semanales, modelo y predicciones';

CREATE VOLUME IF NOT EXISTS workspace.equipo6_bronze.crudos
COMMENT 'Equipo 6 - archivos crudos: fotos/, complementarias/mem/, complementarias/fred/ y checkpoints de Auto Loader';

-- COMMAND ----------

-- MAGIC %md ## Bronce

-- COMMAND ----------

CREATE TABLE IF NOT EXISTS workspace.equipo6_bronze.fotos_precios (
  path                 STRING    COMMENT 'Ruta completa de la foto (llave natural)',
  modificationTime     TIMESTAMP COMMENT 'Fecha de modificación del archivo',
  length               BIGINT    COMMENT 'Tamaño en bytes',
  content              BINARY    COMMENT 'Contenido binario de la foto',
  fecha_carpeta        DATE      COMMENT 'Fecha de la carpeta fotos/AAAA-MM-DD/ si existe (si no, NULL: la fecha sale del EXIF en Plata)',
  _ingestion_timestamp TIMESTAMP COMMENT 'Fecha y hora de la carga a Bronce',
  _source_file         STRING    COMMENT 'Ruta de la foto de origen'
)
USING DELTA
COMMENT 'Fotos de precios tal como llegan (Volume crudos/fotos), con columnas de auditoría. Carga incremental (Auto Loader).';

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
COMMENT 'Cuarentena: lecturas que no pasaron las reglas de calidad, con el motivo.';

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ## Oro
-- MAGIC Las tablas Oro las crea `03_gold` con `overwrite` (gestionadas en `workspace.equipo6_gold`).
-- MAGIC La API del servidor las lee con un SQL warehouse (`DATABRICKS_WAREHOUSE_ID`).

-- COMMAND ----------

SHOW TABLES IN workspace.equipo6_bronze;
