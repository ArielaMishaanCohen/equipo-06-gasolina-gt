# Pipelines (Databricks)

Notebooks en formato de Databricks (`# Databricks notebook source`). Se sincronizan con Git folders.

| Orden | Notebook | Dueño | Qué hace |
| --- | --- | --- | --- |
| 0 | `00_setup.sql` | Datos | Esquemas `equipo6_bronze/silver/gold`, Volume `equipo6_bronze.crudos` y tablas gestionadas (una vez). |
| 1 | `01_bronze.py` | Datos | Auto Loader (`binaryFile`) de `raw/img/` → `bronze.fotos_precios`, incremental, con auditoría. |
| 2 | `02_silver.py` | Modelos + Datos | OCR → `silver.precios`; reglas de calidad → `silver.precios_rejected`; MERGE idempotente. |
| 3 | `03_gold.py` | Datos + Modelos | `precio_semanal`, `variacion_semanal`, `features_modelo`; modelo (MLflow), `predicciones`, `metricas_modelo`. |
| — | `04_experimentos_ocr.py` | Modelos | (Opcional) comparación de motores y preprocesamientos en MLflow. |
| — | `job.json` | Datos | Definición exportada del Job `equipo6-pipeline` (Bronce → Plata → Oro). |

Parámetros (widgets): `catalogo`, esquemas, rutas S3 y `umbral_q`. Valores por defecto en
[`config/config.yaml`](../config/config.yaml). Contratos de tablas: sección 5 de
[`docs/instructivos/INSTRUCTIVO_GENERAL.md`](../docs/instructivos/INSTRUCTIVO_GENERAL.md).
