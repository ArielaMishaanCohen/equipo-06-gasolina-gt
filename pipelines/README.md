# Pipelines (Databricks)

Notebooks en formato de Databricks (`# Databricks notebook source`). Se sincronizan con Git folders.

| Orden | Notebook | Dueño | Qué hace |
| --- | --- | --- | --- |
| 0 | `00_setup.sql` | Datos | Esquemas `equipo6_bronze/silver/gold`, Volume `equipo6_bronze.crudos` y tablas gestionadas (una vez). |
| 1 | `01_bronze.py` | Datos | Auto Loader (`binaryFile`) de `raw/img/` → `bronze.fotos_precios`, incremental, con auditoría. |
| 2 | `02_silver.py` | Modelos + Datos | OCR → `silver.precios`; reglas de calidad → `silver.precios_rejected`; MERGE idempotente. |
| 3 | `03_gold.py` | Datos + Modelos | `precio_semanal`, `variacion_semanal`, `features_modelo`; modelo (MLflow), `predicciones`, `metricas_modelo`. |
| — | `04_experimentos_ocr.py` | Modelos | Compara motores y preprocesamientos en MLflow con 20 o más fotos etiquetadas y exporta la configuración recomendada. |
| — | `job.json` | Datos | Definición exportada del Job `equipo-06-pipeline` (Bronce → Plata → Oro). |

Parámetros (widgets): `catalogo`, esquemas, rutas S3 y `umbral_q`. Valores por defecto en
[`config/config.yaml`](../config/config.yaml). Contratos de tablas: sección 5 de
[`docs/instructivos/INSTRUCTIVO_GENERAL.md`](../docs/instructivos/INSTRUCTIVO_GENERAL.md).

El estado de Modelos, los permisos necesarios y los pasos para recuperar resultados están
en [`docs/modelos/CIERRE_MODELOS.md`](../docs/modelos/CIERRE_MODELOS.md).

El Job 637916192930332 usa entorno serverless **2**, programación martes 07:00 de
Guatemala y alertas a los dos correos indicados por el equipo. Ejecuta copias de los
notebooks en Workspace; después del push deben sincronizarse los cambios posteriores.
No se configura todavía una fuente Git remota para código que aún no se ha publicado.
Las dos validaciones completas y el motivo de fijar el entorno están en
[`docs/evidencias_job.md`](../docs/evidencias_job.md).
