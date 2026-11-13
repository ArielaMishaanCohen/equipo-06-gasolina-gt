# Configuración de clusters: interactivo frente a job cluster

*Nota para la sección 5 del informe técnico (Equipo 06).*

## Propósito y costo

| | Cluster interactivo | Job cluster |
| --- | --- | --- |
| **Para qué sirve** | Desarrollo: escribir y probar los notebooks celda por celda, explorar datos y depurar. | Producción: ejecutar el pipeline automático (Job `equipo-06-pipeline`: Bronce, Plata y Oro). |
| **Cuándo existe** | Se enciende a mano y sigue encendido hasta que se apaga o se cumple su autoterminación. | Se crea al iniciar la corrida del Job y se apaga solo al terminar. |
| **Cómo se paga** | Mientras está encendido, aunque nadie lo use; el tiempo ocioso también cuesta. Por eso se configura con autoterminación de **máximo 30 minutos** y se apaga al terminar. | Solo por la duración de la corrida. Además, el cómputo de Jobs se factura con una tarifa menor que el cómputo interactivo. |
| **Quién lo usa** | Una persona, o varias compartiéndolo. | Nadie de forma interactiva: lo lanzan la programación, un disparador o "Run now". |
| **Reproducibilidad** | Depende de lo que cada persona haya instalado o ejecutado antes. | Cada corrida parte de la misma configuración y del código de la rama `main` del repositorio. |

En resumen: el cluster interactivo es un taller de trabajo cuyo costo crece con el tiempo que permanece encendido; el job cluster es una herramienta de un solo uso, creada y destruida por cada ejecución del pipeline, que evita pagar tiempo ocioso y deja cada corrida en un entorno limpio y repetible.

En este proyecto el workspace es Databricks Free Edition, que solo ofrece cómputo *serverless*. El Job `equipo-06-pipeline` usa cómputo serverless de Jobs, que cumple el mismo papel que un job cluster: se aprovisiona para la corrida y no queda nada encendido después. El cluster interactivo se usa únicamente para desarrollar.

## Configuración del cluster interactivo

| Parámetro | Valor |
| --- | --- |
| Versión de Databricks Runtime | [COMPLETAR] |
| Tipo de nodo | [COMPLETAR] |
| Número de workers | [COMPLETAR] |
| Autoterminación (máximo 30 minutos) | [COMPLETAR] minutos |
| Librerías instaladas | Paquete `gasolina` (instalado desde el Git folder): [COMPLETAR]; RapidOCR: [COMPLETAR versión]; MLflow: [COMPLETAR versión] |

## Configuración del cómputo del Job

| Parámetro | Valor |
| --- | --- |
| Tipo de cómputo | Serverless de Jobs (Free Edition) — o job cluster si el catedrático lo indica: [COMPLETAR] |
| Versión de Databricks Runtime / entorno serverless | [COMPLETAR] |
| Tipo de nodo y número de workers (solo si es job cluster) | [COMPLETAR] |
| Programación | Martes a las 7:00, hora de Guatemala |
| Duración de cada tarea (bronze, silver, gold) | [COMPLETAR con la captura del historial de ejecuciones] |

---

## Anexo para el equipo (no va al informe)

**Disparador por llegada de archivos.** `job.json` usa programación semanal porque un Job solo admite un disparador. Si el catedrático prefiere *file arrival*, quita el bloque `schedule` y agrega esto (la ruta es la del widget `ruta_fotos`; la external location debe permitir `READ FILES`):

```json
"trigger": {
  "pause_status": "UNPAUSED",
  "file_arrival": {"url": "s3://cc3105-raw-869227452861-us-east-2-an/img/"}
}
```

**Job cluster en lugar de serverless.** Solo si el workspace permite clusters clásicos: agrega en el Job un bloque `job_clusters` y, en cada tarea, `"job_cluster_key": "pipeline"`. El `[COMPLETAR]` es la versión de runtime, el tipo de nodo y los workers:

```json
"job_clusters": [{
  "job_cluster_key": "pipeline",
  "new_cluster": {
    "spark_version": "[COMPLETAR]",
    "node_type_id": "[COMPLETAR]",
    "num_workers": 0
  }
}]
```
