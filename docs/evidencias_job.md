# Evidencias del Job

Validación real del 15 de noviembre de 2026. Job `equipo-06-pipeline`, ID `637916192930332`.

| Corrida | Bronce / Plata / Oro | Fotos | Rutas distintas | Tiempos Bronce / Plata / Oro |
| --- | --- | --- | --- | --- |
| [337245597755365](https://dbc-f51e9943-f137.cloud.databricks.com/?o=1420684327351409#job/637916192930332/run/337245597755365) | SUCCESS / SUCCESS / SUCCESS | 1 | 1 | 38 / 167 / 139 s |
| [417806436744272](https://dbc-f51e9943-f137.cloud.databricks.com/?o=1420684327351409#job/637916192930332/run/417806436744272) | SUCCESS / SUCCESS / SUCCESS | 2 | 2 | 36 / 144 / 139 s |

Los tiempos corresponden a `execution_duration`; excluyen aprovisionamiento y esperas.
La exportación está en [evidencias_job.json](evidencias_job.json).

## Alcance de la prueba

Se usaron `workspace.equipo6_validacion_bronze`, `equipo6_validacion_silver` y
`equipo6_validacion_gold`, separados de producción. Primero se procesó IMG_7549.HEIC
(7 de enero de 2026); después se añadió IMG_7575.HEIC (13 de enero de 2026).
Son fotos existentes reales del equipo. Se copiaron las fuentes complementarias
originales. Las rutas únicas coinciden con las fotos, incluida la recarga de la primera.

Ambas corridas sobrescriben los parámetros hacia las rutas de validación y usan
`modo=batch_merge`. Prueban la cadena completa y la incorporación mediante MERGE;
no prueban el disparador programado ni Auto Loader en producción. Los valores
predeterminados conservan los esquemas productivos, el Volume original y
`modo=autoloader`. Oro productivo y los experimentos OCR tienen evidencia
independiente en [modelos/CIERRE_MODELOS.md](modelos/CIERRE_MODELOS.md).

## Error inicial y corrección

La corrida `634859031002294` falló en Silver. El entorno predeterminado nuevo
utilizó Python 3.12; las restricciones de dependencias dejaron protobuf incompatible
con Spark Connect. Se fijó explícitamente el entorno serverless 2 para las tres
tareas. Las dos corridas de la tabla son posteriores a la corrección. El correo
recibido corresponde al intento fallido y confirma la recepción de la alerta.

La programación está habilitada los martes a las 07:00 de Guatemala, con alertas
a sot22737@uvg.edu.gt y mis22052@uvg.edu.gt. No se ha esperado una ejecución
programada. La definición exportada está en [job.json](../pipelines/job.json).

Los notebooks están en `/Shared/Proyecto/Notebooks/Pipeline_entrega_20261115/`.
El código se instaló como wheel 0.2.0 desde el Volume. Son copias del Workspace:
el push local posterior no las actualiza automáticamente.

## Capturas

- [Historial de ejecuciones del Job](capturas/10_job_historial.png): dos corridas exitosas y el intento fallido corregido.
- [Tareas Bronce → Plata → Oro y su duración](capturas/11_job_tareas_duracion.png) (corrida 417806436744272: 38 s, 2 min 25 s y 2 min 20 s).
- [Programación semanal](capturas/12_job_programacion_alertas1.png) y [alertas por correo](capturas/12_job_programacion_alertas2.png).
- [Experimento de MLflow](capturas/13_mlflow_experimento.png), [tablas Oro](capturas/14_tablas_oro.png) y [predicciones](capturas/15_predicciones_oro.png).
- Capturas de la API y el panel: [docs/capturas/](capturas/README.md).

## API pública

La API está publicada en `http://159.65.111.14:8000` (Swagger en `/docs`) y lee Oro
mediante el SQL warehouse; `/health` responde `fuente_oro=databricks`. Oro sigue en
tablas gestionadas porque las ubicaciones S3 del curso son de solo lectura; el
catedrático aprobó el 13 de noviembre el workspace propio con lectura por SQL warehouse.

## Lectura de fotos por external location (16 nov)

Corrida completa con las tres tareas sobre los esquemas `workspace.equipo_06_*`, con las fotos
leídas directamente de `s3://cc3105-raw-869227452861-us-east-2-an/img/` (external location `xloc-raw`):
[602882162126731](https://dbc-f51e9943-f137.cloud.databricks.com/?o=1420684327351409#job/35821178713934/run/602882162126731),
SUCCESS / SUCCESS / SUCCESS en 69 / 732 / 152 s.

| Tabla | Filas |
| --- | --- |
| `equipo_06_bronze.fotos_precios` | 110 (= fotos de la carpeta, 0 duplicados) |
| `equipo_06_silver.precios` | 221 (2023: 37, 2024: 35, 2025: 56, 2026: 93) |
| `equipo_06_silver.precios_rejected` | 26 (14 sin precios legibles, 6 consistencia, 5 confianza, 1 rango) |
| `equipo_06_gold.precio_semanal` | 461 (197 de fotos desde dic 2022 + 264 del MEM) |

Exactitud manual sin cambios: 78/85 precios correctos (91.8%) en 36 fotos. Métricas del modelo y
predicciones idénticas a la corrida anterior, porque el clasificador entrena con la serie del MEM.

La escritura en `xloc-cusn`, `xloc-ag` y `xloc-au` se probó el mismo día y Databricks respondió
`PERMISSION_DENIED: User cannot write to a read-only external location`. Por eso las tablas siguen
gestionadas. Respaldo del Job anterior: [`respaldo/job_antes_s3_20261116.json`](respaldo/job_antes_s3_20261116.json);
`python scripts/dbx_job.py aplicar | revertir | correr`.
