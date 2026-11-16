# Capturas de evidencia

Tomadas el 15 de noviembre de 2026 contra el servidor real (`http://159.65.111.14:8000`).
El video de respaldo de la demo (`demo_api_respaldo.mp4`, 87 s) no está en Git por su tamaño.

## API y panel (generadas automáticamente)

| Archivo | Qué muestra |
| --- | --- |
| `01_panel_inicio.png` | Panel: precio actual, gráfica MEM vs. fotos, predicción |
| `02_precio_y_prediccion.png` | Evolución del precio y dirección de la semana siguiente |
| `03_modelo_y_conexion.png` | Métricas contra la línea base y lectura de las tablas Oro |
| `04_como_funciona.png` | Recorrido Bronce → Plata → Oro → API |
| `05_historico.png` | Histórico semanal con filtros |
| `06_api_prediccion.png` | Respuesta JSON de `/prediccion?combustible=super` |
| `07_panel_movil.png` | Panel en un teléfono |
| `08_swagger_docs.png` | Documentación interactiva en `/docs` |
| `09_consultas_api.png` / `.txt` | `tests/consultas_api.sh` desde una computadora externa: 7 consultas HTTP 200 |

## Databricks (tomadas a mano con la sesión del equipo)

| Archivo | Qué muestra |
| --- | --- |
| `10_job_historial.png` | Historial de ejecuciones del Job `equipo-06-pipeline` |
| `11_job_tareas_duracion.png` | Una corrida con las tareas Bronce → Plata → Oro y su duración |
| `12_job_programacion_alertas1.png` | Programación semanal: martes 07:00, America/Guatemala |
| `12_job_programacion_alertas2.png` | Notificación por correo si el Job falla |
| `13_mlflow_experimento.png` | Corridas de MLflow comparando modelos y línea base |
| `14_tablas_oro.png` | Esquema `equipo_06_gold` en Catalog con sus tablas |
| `15_predicciones_oro.png` | Datos de `equipo_06_gold.predicciones` |
