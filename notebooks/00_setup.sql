-- Databricks notebook source
-- Crea esquemas y volúmenes de la arquitectura medallion (sección 8.2.1 del instructivo).
-- Si el catálogo no es "workspace", cámbialo aquí y en config/config.yaml.

-- COMMAND ----------

CREATE SCHEMA IF NOT EXISTS workspace.g6_bronce;
CREATE SCHEMA IF NOT EXISTS workspace.g6_plata;
CREATE SCHEMA IF NOT EXISTS workspace.g6_oro;

-- COMMAND ----------

CREATE VOLUME IF NOT EXISTS workspace.g6_bronce.crudos;
CREATE VOLUME IF NOT EXISTS workspace.g6_oro.artifacts;

-- COMMAND ----------

-- Con external location de S3, usar en su lugar:
-- CREATE EXTERNAL VOLUME IF NOT EXISTS workspace.g6_bronce.crudos LOCATION 's3://NOMBRE-BUCKET/g6/bronce/';
-- CREATE EXTERNAL VOLUME IF NOT EXISTS workspace.g6_oro.artifacts LOCATION 's3://NOMBRE-BUCKET/g6/oro/artifacts/';

SHOW VOLUMES IN workspace.g6_bronce;
