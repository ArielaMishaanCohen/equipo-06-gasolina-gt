# Extracción y modelo de predicción · Equipo 6

Borrador para revisión y cierre del informe. Responsable de validación y documentación
por completar. El modelo se ejecutó correctamente en Databricks el 15 de noviembre de 2026
a las 13:41, hora de Guatemala. La comparación de las cuatro variantes OCR también terminó
correctamente en Databricks el mismo día.

## Método de extracción

El pipeline procesa fotos JPG, PNG y HEIC desde Bronce. Lee la fecha y las coordenadas
del EXIF y utiliza la fecha de carpeta cuando falta la fecha original. RapidOCR reconoce
el texto y los números. Se comparan cuatro tratamientos de imagen, correspondientes
a la imagen original, contraste local en gris, contraste ampliado y binarización.

Las reglas asignan precios a súper, regular y diésel mediante las etiquetas cercanas.
En las bombas, una segunda lectura de los recortes mejora la resolución de los números.
La relación entre el total de la venta y los galones permite verificar una lectura.
Los precios de V-Power se descartan según el catálogo del proyecto.

Las lecturas pasan a Plata con fecha, combustible, modalidad, ubicación, confianza,
versión y foto de origen. Las reglas de calidad revisan el rango de precio, el combustible,
la fecha y otras condiciones documentadas en `gasolina.calidad`. Los rechazos conservan
el motivo para facilitar su revisión.

## Calidad de la extracción

La tabla reúne los conteos de `02_silver` y los artefactos de `04_experimentos_ocr`.

| Indicador | Resultado real |
| --- | --- |
| Fotos con etiquetas existentes del equipo | 36 |
| Precios legibles etiquetados | 85 |
| Precios extraídos correctamente | 78 |
| Exactitud de precios, diferencia menor que Q0.005 | 91.8% |
| Porcentaje de fotos con todos los precios etiquetados correctos | 80.6% |
| Precios con valor incorrecto | 6 |
| Precios no encontrados | 1 |
| Salidas duplicadas para llaves etiquetadas | 0 |
| Lecturas adicionales sin etiqueta manual | 10 |
| Filas rechazadas por calidad y porcentaje de rechazo | 3 de 96, equivalentes a 3.125% |
| Motor y preprocesamiento recomendados | RapidOCR con `gris_clahe` |
| Corrida OCR elegida | `6e8bec15719a42d9a6a0890eba503476` |

| Preprocesamiento | Precios correctos | Exactitud | Fotos completas |
| --- | --- | --- | --- |
| Gris con CLAHE | 78/85 | 91.8% | 80.6% |
| Gris con CLAHE ampliado al doble | 77/85 | 90.6% | 77.8% |
| Imagen original | 75/85 | 88.2% | 72.2% |
| Binarización | 44/85 | 51.8% | 30.6% |

La ampliación al doble superó el límite de 1 GB por función Python en serverless. Se completó
en el driver procesando una foto a la vez. Las dos corridas terminadas previamente se
reutilizaron después de verificar la coincidencia de sus etiquetas y la versión del paquete.
Las latencias entre driver y workers son orientativas y se excluyeron del desempate.
La configuración elegida coincide con la que ya usa Plata.

El experimento contiene las métricas, los CSV por foto y el YAML recomendado.
[Experimento OCR](https://dbc-f51e9943-f137.cloud.databricks.com/?o=1420684327351409#mlflow/experiments/2721478214756473)

La exactitud utiliza todos los precios etiquetados como denominador. Los precios de fotos
ausentes se consideran no encontrados. Las lecturas sin etiqueta manual requieren revisión.
Los falsos positivos reportados corresponden a salidas duplicadas para el mismo combustible
en una foto con referencia manual, bajo el supuesto de un precio por combustible/foto.

Las tablas de Plata contienen 93 filas aceptadas de 36 fotos y tres rechazos. Dos rechazos
corresponden a fotos sin precios legibles y uno a confianza inferior al umbral configurado.
Estas cifras se recuperaron del workspace antes de incorporar la recomendación de los
nuevos experimentos de preprocesamiento.

El detalle de la nueva corrida con `gris_clahe` permite identificar estos errores concretos.

| Foto | Combustible | Precio etiquetado | Resultado OCR |
| --- | --- | --- | --- |
| `IMG_7575.HEIC` | Diésel | Q24.89 | Sin detección |
| `IMG_8064.HEIC` | Regular | Q35.16 | Q35.76 |
| `IMG_8636.HEIC` | Diésel | Q41.69 | Q47.69 |

En la prueba preliminar local también hubo dígitos de siete segmentos parcialmente tapados.
Las cinco fotos locales produjeron registros en cuatro imágenes. La comparación oficial
utiliza las etiquetas existentes del equipo y conserva el detalle por foto para su revisión.

## Variables y objetivo del modelo

El objetivo es la dirección del precio de la semana siguiente para súper, regular y diésel.
Las semanas empiezan el martes y terminan el lunes. La dirección es `sube` cuando la
variación supera Q0.10 y `baja` cuando es menor que −Q0.10. Los demás cambios se clasifican
como `se_mantiene`.

Las variables incluyen las últimas cuatro variaciones semanales, el promedio móvil de
cuatro semanas, la diferencia de precio entre súper y diésel y la dirección actual.
El combustible se representa mediante one-hot. La variación del WTI y el subsidio activo
se incorporan cuando hay datos. Los valores faltantes numéricos se imputan con la mediana
calculada sobre el entrenamiento, junto con indicadores de ausencia.

## Evaluación temporal y comparación

Se reservan las últimas diez semanas con objetivo y dirección actual conocidos para la
prueba. Las semanas anteriores forman el entrenamiento. Se comparan una regresión
logística y un árbol de decisión contra la regla que repite la dirección de la semana actual.
El candidato de mayor F1 macro se elige cuando supera estrictamente a esa regla.

| Modelo | Accuracy | F1 macro | Supera a la línea base | Corrida MLflow |
| --- | --- | --- | --- | --- |
| Línea base | 0.5000 | 0.2564 | Referencia | `239d57a004384a0baeffd5481a573df1` |
| Regresión logística | 0.6000 | 0.3130 | Sí | `826b0bb0449e4e7ba1b19632926065dc` |
| Árbol de decisión | 0.4333 | 0.3056 | Sí, según F1 macro | `bb76abcd3714407baecb74e291330778` |

Se usaron 183 registros para entrenar y 30 para probar. Las diez semanas de prueba son
30 de junio, 7, 14, 21 y 28 de julio, 4, 11 y 18 de agosto y 22 y 29 de septiembre de 2026.
El conjunto de prueba contiene 18 casos de subida, ocho de bajada y cuatro de estabilidad.
La regresión logística resulta elegida. Su matriz de confusión muestra cero aciertos en
`se_mantiene`, una limitación que explica el F1 macro bajo a pesar del 60% de accuracy.

El elegido se reentrena con las observaciones disponibles y se guarda como artefacto de
MLflow, incluida la línea base cuando resulta ganadora. Se intenta registrarlo en Unity
Catalog. Las tablas Oro guardan las predicciones, los identificadores de corrida, las
métricas y la dirección observada cuando ya está disponible.

## Predicción entregada

| Combustible | Semana objetivo | Dirección | Probabilidad | Dirección de la línea base |
| --- | --- | --- | --- | --- |
| Súper | 2026-11-10 | baja | 0.8139 | Sin dato |
| Regular | 2026-11-10 | baja | 0.8613 | Sin dato |
| Diésel | 2026-11-10 | baja | 0.8908 | Sin dato |

Estas predicciones se generaron el 15 de noviembre de 2026 a las 19:41:25 UTC con la corrida
final `77ea6e78af404002bfa856a1fe6ab69a`. El histórico termina el 3 de noviembre de 2026.
Para generar la predicción del 17 de noviembre se necesita incorporar la semana del 10.
La fecha objetivo conserva el cálculo basado en la última semana disponible.

## Limitaciones e interpretación

Una historia corta y las semanas faltantes reducen las observaciones disponibles. Los
cambios de subsidio pueden alterar la relación entre las variables y la dirección del precio.
La comparación y la selección utilizan las mismas semanas de prueba, por lo que existe
sesgo de selección. La evaluación con semanas posteriores permitirá medir el rendimiento
del modelo elegido en datos futuros.

Una línea base sin dirección actual conocida carece de predicción para ese combustible.
Ese caso necesita revisar el histórico y queda señalado por el notebook. La cobertura de
los tres combustibles debe verificarse antes de entregar.

La revisión local obtuvo 143 pruebas aprobadas y una omitida por ausencia de PySpark.
También aprobaron el análisis de Ruff y la compilación de Python. La ejecución completa
de Oro con Spark y MLflow terminó con estado `SUCCESS`. Los CSV de métricas y predicciones
se descargaron a `artifacts/databricks/` para conservar la evidencia.

La ejecución de Oro se puede consultar en el workspace del equipo.
[Ejecución validada](https://dbc-f51e9943-f137.cloud.databricks.com/?o=1420684327351409#job/179065592137118/run/31229731884243)

El experimento de clasificación contiene las corridas de evaluación y del modelo final.
[Experimento MLflow](https://dbc-f51e9943-f137.cloud.databricks.com/?o=1420684327351409#mlflow/experiments/2721478214756472)

## Cierre de la contribución

Revisar las tablas, contrastar los resultados y explicar el modelo elegido. Copiar este
documento a `docs/modelos/RESULTADOS_MODELOS.md` en una rama propia y hacer el commit
con la cuenta del integrante que realiza esa validación. Las secciones de método y
resultados pueden incorporarse después al informe general de máximo cinco páginas.
