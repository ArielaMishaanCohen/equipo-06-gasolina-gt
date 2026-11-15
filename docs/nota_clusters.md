# Cómputo utilizado

El Job usa serverless de Jobs. No se encontraron clusters clásicos en el inventario
consultado. La plataforma administra nodos, workers y ciclo de vida del cómputo.

| Parámetro | Valor comprobado |
| --- | --- |
| Job | equipo-06-pipeline, 637916192930332 |
| Entorno serverless | 2, explícito en las tres tareas |
| Python de la prueba de entorno | 3.11.10 |
| Spark informado por la sesión remota | 4.2.0 |
| Paquete | gasolina 0.2.0, wheel en el Volume |
| OCR | RapidOCR ONNX Runtime 1.3.24, gris_clahe |
| Restricciones de Plata y Oro | numpy >=1.26,<2; pandas >=2,<3; protobuf >=4.25.3,<5 |
| Programación | Martes 07:00, America/Guatemala |
| Primera ejecución: Bronce / Plata / Oro | 38 / 167 / 139 segundos |
| Segunda ejecución: Bronce / Plata / Oro | 36 / 144 / 139 segundos |

Las duraciones excluyen aprovisionamiento y esperas. Enlaces y alcance en
[evidencias_job.md](evidencias_job.md). No se dispone de consumo monetario real.
La versión del entorno serverless no equivale a una versión de Databricks Runtime
clásico. La [documentación de entornos](https://docs.databricks.com/aws/en/release-notes/serverless/environment-version/)
describe las dependencias base; los notebooks instalan además sus restricciones.

Un cluster interactivo clásico sirve para desarrollo y requiere controlar tiempo
ocioso y autoterminación. Un cluster de Jobs clásico se aprovisiona para la corrida.
Esta entrega usa serverless y no ha desplegado esas variantes clásicas. Ejecuta
copias del Workspace, sin enlace todavía al código remoto sin publicar de
`modelos-completar`.

Fijar el entorno 2 resolvió la incompatibilidad inicial de Silver. Las dos corridas
posteriores terminaron en SUCCESS.
