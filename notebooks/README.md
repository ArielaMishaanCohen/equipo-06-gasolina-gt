# Notebooks (Databricks)

Orden de ejecución:

| # | Notebook | Dueño | Qué hace |
| --- | --- | --- | --- |
| 00 | `00_setup.sql` | Datos | Crea esquemas `g6_bronce`, `g6_plata`, `g6_oro` y volúmenes `crudos` y `artifacts`. |
| 01 | `01_bronce_ingesta` | Datos | Descarga FRED a bronce e inventario de archivos crudos. |
| 02 | `02_plata` | Datos | Fotos → `lecturas_ocr`; MEM → `precios_mem`; FRED → `exogenas_diarias`. |
| 03 | `03_oro` | Datos | `precios_estacion`, `comparacion_mem`, `features_forecast`; exporta `reglas.json` e `historico.json`. |
| 04 | `04_experimentos_ocr` | Modelos | Experimentos MLflow del OCR; exporta `ocr_config.json`. |
| 05 | `05_forecast` | Modelos | Pronóstico; exporta `forecast.joblib`, `forecast_meta.json`, `predicciones.json`. |
| 06 | `06_monitoreo` | Datos | Logs de la API → `api_predicciones` y `monitoreo_diario`; exporta `monitoreo.json`. |

Los artifacts van a `/Volumes/workspace/g6_oro/artifacts/` con los contratos de la sección 4.2 de
`docs/INSTRUCTIVO_GENERAL.md`. La API los descarga con `gasolina-sync descargar`.
