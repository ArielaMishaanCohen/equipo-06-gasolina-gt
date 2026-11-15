# Cierre de Modelos · Equipo 6

Revisión del 15 de noviembre de 2026. Se contrastaron la guía `3_MODELOS.md`, el instructivo
general v3 y el enunciado oficial del repositorio con el código y las pruebas locales.

## Resultados verificados en Databricks

Se validó la conexión de `sot22737@uvg.edu.gt` al workspace del equipo y se ejecutó
`03_gold` con estado `SUCCESS`. La ejecución registró experimentos y el modelo final en
MLflow y actualizó las tablas de métricas y predicciones. Los comentarios de ambas tablas
y de todas sus columnas están completos.
[Ejecución de Oro](https://dbc-f51e9943-f137.cloud.databricks.com/?o=1420684327351409#job/179065592137118/run/31229731884243)

| Modelo | Accuracy | F1 macro |
| --- | --- | --- |
| Línea base | 0.5000 | 0.2564 |
| Regresión logística, elegida | 0.6000 | 0.3130 |
| Árbol de decisión | 0.4333 | 0.3056 |

El entrenamiento utiliza 183 registros y la prueba 30 registros de diez semanas. El
histórico contiene 264 filas, desde el 26 de noviembre de 2024 hasta el 3 de noviembre de 2026.
La última fecha disponible produce predicciones para el 10 de noviembre. Para entregar una
predicción del 17 de noviembre se requiere que Datos incorpore la semana del 10.

Bronce contiene 38 fotos y el CSV existente del equipo etiqueta 36 fotos con 85 precios.
La comparación final registra 78 aciertos, seis valores incorrectos y un precio no
encontrado con `gris_clahe`, equivalente a 91.8%. Plata tiene 93 registros aceptados y tres
rechazos. El experimento OCR completo terminó con estado `SUCCESS`.
[Ejecución de OCR](https://dbc-f51e9943-f137.cloud.databricks.com/?o=1420684327351409#job/640585771730337/run/555603084915275)

| Preprocesamiento RapidOCR | Precios correctos | Exactitud | Fotos completas |
| --- | --- | --- | --- |
| `gris_clahe`, recomendado | 78/85 | 91.8% | 80.6% |
| `gris_clahe_x2` | 77/85 | 90.6% | 77.8% |
| `ninguno` | 75/85 | 88.2% | 72.2% |
| `binarizado` | 44/85 | 51.8% | 30.6% |

La recomendación coincide con la configuración existente. El CSV comparativo, los detalles
por foto y el YAML recomendado se guardaron en MLflow y se descargaron en
`artifacts/databricks/experimentos_ocr/`.

Los respaldos de tablas, CSV y respuestas de ejecución están en `artifacts/databricks/`.
El borrador reservado para el compañero incorpora las cifras recuperadas del workspace.

La validación detectó un límite de 1 GB por función Python de serverless al usar la imagen
ampliada al doble. El notebook de experimentos procesa ahora una foto a la vez en el driver.
Puede reanudar corridas terminadas mediante `run_ids_reutilizar`, verificando que coincidan
la versión y las etiquetas. Las latencias de driver y workers se reportan como orientativas
y se excluyen del desempate cuando se mezclan ambos entornos.

Los notebooks fijan rangos compatibles de NumPy, pandas y Protobuf para conservar la
compatibilidad con el MLflow del runtime. La configuración explícita del registro evita
consultar propiedades de Spark que serverless restringe.

## Estado encontrado

| Entrega | Estado al revisar | Trabajo en esta entrega |
| --- | --- | --- |
| Metadata JPG, PNG y HEIC | Implementada con pruebas | Verificada localmente, incluida una foto con EXIF real |
| RapidOCR, EasyOCR opcional y cuatro preprocesamientos | Implementados | Prueba real del OCR sobre los cinco JPG disponibles |
| Reglas de números, combustibles, modalidad y asociación espacial | Implementadas | Corrección del filtrado de rótulos verticales, tablas MEM y palabras separadas de modalidad |
| Extracción a Plata y exactitud en `02_silver` | Implementadas en `main` | Pruebas de integración y validación de etiquetas no finitas |
| Evaluación local | Implementada parcialmente | Rechazo de etiquetas y nombres ambiguos, conteo de duplicados, comparación de preprocesamientos y exportación JSON |
| Experimentos de OCR | Notebook ausente | Implementado y ejecutado correctamente en Databricks con las cuatro variantes |
| Clasificador y línea base | Implementados con validación temporal | Validación de entradas, entrenamiento de una sola clase y predicción con poco histórico |
| MLflow y tablas de predicción | Implementados en `03_gold` | Registro del artefacto de la línea base y explicación de candidatos omitidos |
| Exactitud de 20 o más fotos oficiales | Evidencia verificada | 36 fotos y 85 precios, con 91.8% de acierto confirmado en la nueva comparación |
| Resultados del modelo sobre histórico real | Ejecución verificada | Oro terminó correctamente y la regresión logística obtuvo 0.60 de accuracy |

`src/gasolina/forecast.py` corresponde a la regresión de la versión 2. La entrega vigente usa
`src/gasolina/modelo.py`, cuyo objetivo es `direccion_siguiente`.

Los nombres predeterminados actuales son `workspace.equipo6_bronze`, `equipo6_silver` y
`equipo6_gold`. Las guías recibidas también mencionan `equipo_06`. Confirmar los nombres
existentes antes de ejecutar SQL.

## Acceso a Databricks que necesitamos

Los permisos de lectura de Plata y Oro se comprobaron después de que el equipo los
habilitó. El SQL de referencia para reproducir esos permisos se encuentra en
`docs/modelos/PERMISOS_DATABRICKS.sql`.

Comparte este pedido con la persona que administra el workspace del equipo.

> Necesitamos acceso al workspace de Databricks del equipo con nuestra propia cuenta.
> Necesitamos abrir y actualizar el Git folder del proyecto y ejecutar los notebooks
> `02_silver`, `03_gold` y `04_experimentos_ocr` en el cómputo disponible del curso.
> Necesitamos leer `workspace.equipo6_bronze.fotos_precios`, las tablas complementarias de
> Bronce, las tablas de Plata y `workspace.equipo6_gold.features_modelo`.
> Necesitamos escribir en los esquemas de Plata y Oro, leer el CSV de etiquetas y escribir
> reportes y wheels en `/Volumes/workspace/equipo6_bronze/crudos`.
> Necesitamos crear y registrar corridas en nuestros experimentos MLflow.
> Por favor compartir la URL del workspace, el cómputo que debemos usar y la ruta de
> `etiquetas.csv` y de las fotos oficiales. También confirmar si Oro debe guardarse en S3.

En Unity Catalog estos accesos suelen corresponder a `USE CATALOG`, `USE SCHEMA`, `SELECT`,
`CREATE TABLE`, `MODIFY`, `READ VOLUME` y `WRITE VOLUME`, según el recurso utilizado.
Registrar el modelo en UC también requiere permisos sobre el esquema y el modelo. Si ese
registro falla, `03_gold` conserva el artefacto en la corrida de MLflow.

También puede ejecutar los notebooks una persona que ya tenga acceso. Necesitamos que
devuelva los resultados indicados más abajo. Las credenciales personales se configuran
en el entorno de esa persona.

## Comprobar lo que ya hay en el workspace

Ejecutar en SQL y guardar la salida. Si una tabla falta, continuar con las otras consultas
y coordinar con Datos la carga correspondiente.

```sql
SHOW TABLES IN workspace.equipo6_bronze;
SHOW TABLES IN workspace.equipo6_silver;
SHOW TABLES IN workspace.equipo6_gold;
SELECT count(*) AS fotos FROM workspace.equipo6_bronze.fotos_precios;
SELECT combustible, count(*) AS filas,
       min(semana_inicio) AS primera_semana, max(semana_inicio) AS ultima_semana
FROM workspace.equipo6_gold.features_modelo GROUP BY combustible;
SELECT * FROM workspace.equipo6_gold.metricas_modelo
ORDER BY fecha_entrenamiento DESC;
SELECT * FROM workspace.equipo6_gold.predicciones
ORDER BY semana_objetivo DESC;
```

Antes de reemplazar resultados existentes, exportar la tabla de métricas, las predicciones
y los enlaces de MLflow para poder compararlos con la nueva ejecución.

## Ejecutar y recuperar evidencia

1. Subir la rama `modelos-completar` y seleccionarla en un Git folder de Databricks.
   Confirmar con Datos que `00_setup` y `01_bronze` ya se ejecutaron.
2. Revisar al menos 20 fotos oficiales y completar `etiquetas.csv`. Cada fila lleva
   `foto,fecha,combustible,modalidad,ubicacion,precio_q_galon`. Anotar los precios legibles
   y documentar las lecturas dudosas. El evaluador actual admite un precio por combustible
   en cada foto. Una tabla con varias modalidades por combustible necesita un recorte
   identificado por modalidad para preparar su evaluación.
3. Ejecutar `04_experimentos_ocr` con `ruta_etiquetas` apuntando al CSV revisado.
   Usar inicialmente `motores=rapidocr`. Agregar `easyocr` cuando su extra esté instalado
   en driver y workers. El notebook registra su omisión si falta la instalación.
4. Descargar `comparativa_ocr.csv`, los CSV por foto, `seleccion.json` y
   `config_extraccion_recomendada.yaml` desde MLflow o `ruta_salida`.
   El experimento se crea en `/Users/<usuario>/equipo06_ocr`.
   Entregar el YAML a Producción para incorporar la recomendación en la configuración.
5. Ejecutar `02_silver` con el motor y preprocesamiento recomendados,
   `reprocesar=true`, `ruta_etiquetas` y una `ruta_reporte_exactitud` propia del equipo.
   La misma versión del paquete conserva el número `0.2.0`, por lo que se necesita
   reprocesar para aplicar los cambios de extracción. Guardar el resumen de exactitud,
   rechazos, conteos e idempotencia que muestra el notebook.
6. Ejecutar `03_gold` con `n_semanas_test=10`. Necesita al menos 14 semanas con objetivo
   y dirección actual conocidos. Guardar la tabla comparativa de modelos, el modelo
   elegido, las matrices de confusión y las corridas de
   `/Users/<usuario>/equipo06_direccion`. Si una semana falta, revisar el histórico con Datos.
7. Descargar `gold.metricas_modelo` y `gold.predicciones`. Comprobar una sola fila marcada
   `es_champion`, una predicción para cada combustible esperado y una semana objetivo
   que sea el martes posterior a la última semana del histórico.
8. Volver a ejecutar el Job y recuperar las dos ejecuciones exitosas exigidas por el curso
   junto con Datos. Incorporar las cifras reales en el documento de resultados.

Para una predicción de la semana del 17 de noviembre de 2026, la última semana disponible
en las variables debe empezar el 10 de noviembre de 2026. El código calcula la fecha desde
los datos, por lo que una serie atrasada producirá una predicción para una semana atrasada.

## Criterios de interpretación

La exactitud de OCR es `100 * precios_correctos / precios_etiquetados`, con diferencia
estrictamente menor que Q0.005. Las fotos ausentes cuentan como precios no encontrados.
`sin_etiqueta` cuenta lecturas para combustibles sin referencia manual. `falsos_positivos`
cuenta salidas duplicadas para una llave foto/combustible etiquetada. Este indicador requiere
que el conjunto etiquete un precio por combustible en cada foto.

El modelo usa las últimas diez semanas con objetivo conocido para la prueba y las anteriores
para entrenar. La imputación se ajusta con el entrenamiento. Se elige el mayor F1 macro
solo cuando supera estrictamente a la línea base. La selección usa esa misma prueba
temporal, por lo que las métricas describen la comparación y tienen sesgo de selección.
Conservar una evaluación futura permitirá medir la generalización del modelo elegido.

La línea base necesita `direccion_actual`. Cuando ese dato falta en la última semana,
se omite esa predicción y el notebook avisa qué combustible falta. Un clasificador entrenado
puede predecir con las variables imputadas. La probabilidad de la línea base permanece nula.

## Validación local

El entorno se instaló desde `uv.lock`. Se verificaron Ruff, compilación de Python y las
pruebas automatizadas. El resultado final fue 143 pruebas aprobadas y una omitida porque
PySpark está ausente del entorno local. Ruff y la compilación de Python aprobaron.
En Windows aparece un conflicto de DLL cuando ONNX Runtime se carga
después de las librerías de las tablas Delta. La suite completa se ejecutó cargándolo primero.

```powershell
.venv/Scripts/ruff.exe check .
.venv/Scripts/python.exe -m compileall -q src pipelines tests
.venv/Scripts/python.exe -c "import onnxruntime; import pytest; raise SystemExit(pytest.main(['-q', '-p', 'no:cacheprovider']))"
```

Para comparar OCR localmente cuando estén las etiquetas revisadas y las fotos completas,
se puede ejecutar el siguiente comando. `--salida` conserva el detalle aunque la consola
muestre un resumen.

```powershell
.venv/Scripts/gasolina-evaluar.exe --etiquetas ../datos/etiquetas.csv --imagenes ../datos --comparar-preprocs --salida artifacts/evaluacion_ocr.json
```

La prueba real de las cinco fotos locales generó `artifacts/prueba_ocr_local.json`.
Produjo registros en cuatro fotos y ningún registro en `IMG_8304.jpg`. Algunas lecturas
requieren revisión por dígitos tapados o confundidos en pantallas de siete segmentos.
La evaluación de las fotos oficiales se completó después usando las 36 fotos etiquetadas
del equipo, cuyos resultados se presentan al inicio de esta guía.

## Entrega separada para el compañero

El borrador está en `artifacts/entrega_companero/RESULTADOS_MODELOS.md`, una carpeta ignorada
por Git. Puede revisarlo, incorporar los resultados reales y copiarlo a
`docs/modelos/RESULTADOS_MODELOS.md` para hacer su commit. Su aporte queda en la revisión,
interpretación de resultados y documentación de evidencia.

Para tu primer commit se pueden agregar explícitamente los archivos de código y pruebas
de esta entrega, `pipelines/03_gold.py`, `pipelines/04_experimentos_ocr.py` y este documento.
Usar `git status --short` y `git diff` antes de hacer commit. La rama preparada es
`modelos-completar`. El push lo realiza el integrante desde su propia cuenta.

```powershell
git add src/gasolina tests pipelines/03_gold.py pipelines/04_experimentos_ocr.py pipelines/README.md docs/README.md docs/modelos/CIERRE_MODELOS.md docs/modelos/PERMISOS_DATABRICKS.sql
git diff --cached --stat
git commit -m "modelos: completar experimentos OCR y robustecer clasificacion temporal"
git push -u origin modelos-completar
```

## Hallazgos de otras partes del proyecto

Datos y Producción deben confirmar el almacenamiento externo de tablas Oro en S3, pues
los notebooks actuales admiten tablas gestionadas cuando las rutas se dejan vacías.
El Job ya tiene los dos correos del equipo y entorno serverless 2 explícito. Las dos
ejecuciones completas terminaron en SUCCESS con una y dos fotos reales, respectivamente,
en esquemas de validación separados. Los enlaces y tiempos están en
[`../evidencias_job.md`](../evidencias_job.md). El informe y los dos PDF del jurado están
generados. Quedan el despliegue público por la responsable de SSH y la confirmación
del almacenamiento frente al requisito original de S3 directo.

## Referencias de implementación

El registro de la línea base sigue la interfaz `PythonModel` y utiliza un ejemplo y una
firma de entrada y salida. [MLflow PythonModel](https://mlflow.org/docs/latest/ml/model/python_model/)
