# Contenido completo para rehacer la presentación

Proyecto: **Precios de combustible en Guatemala**. Equipo 06, ML Engineering, CC3105.

Integrantes: Alina Carias, Marcos Diaz, Daniel Machic, Ignacio Mendez, Ariela Mishaan y Diego Soto.

Fecha de corte de las cifras y del estado operativo: **15 de noviembre de 2026**.
Actualizar la fecha de portada al día de exposición. Este documento es una fuente
editable para crear otra presentación en PowerPoint, Google Slides, Canva u otra
herramienta. No depende del diseño de los PDF anteriores.

## 1. Cómo utilizar este documento

La presentación debe explicar el proyecto a un jurado que no conoce el curso:
problema → arquitectura → foto a dato → modelo frente a la base → operación → demo → lecciones.

La estructura propuesta contiene **10 diapositivas para 10 minutos**, seguidas de
**5 minutos de demostración y 5 minutos de preguntas**. Todos los integrantes deben
hablar. El reparto siguiente es una sugerencia para exponer; no atribuye la autoría
del código a una persona.

| Diapositiva | Tema | Tiempo | Expositor sugerido |
| --- | --- | --- | --- |
| 1 | Problema y objetivo | 30 s | Alina |
| 2 | Arquitectura | 60 s | Alina |
| 3 | Datos y trazabilidad | 60 s | Marcos |
| 4 | Evaluación del OCR | 75 s | Daniel |
| 5 | Calidad y errores | 60 s | Marcos |
| 6 | Objetivo y variables del modelo | 75 s | Ignacio |
| 7 | Comparación de modelos | 90 s | Ignacio |
| 8 | Automatización y evidencia | 60 s | Ariela |
| 9 | Predicción y API | 60 s | Diego |
| 10 | Lecciones y alcance | 30 s | Diego |
| Total | Exposición | 600 s | 10 minutos |

Separar el texto visible de las notas: los párrafos de explicación son para quien
expone, no para pegarlos completos en las diapositivas. Usar formato 16:9, texto
legible desde lejos, títulos concretos y gráficos con unidades. Mantener los
detalles de implementación y enlaces largos en las notas o en un apéndice.

## 2. Diapositivas propuestas

### Diapositiva 1. De una foto a una predicción semanal

**Texto visible**

> Precios de combustible en Guatemala
>
> Transformamos fotos en datos consultables y estimamos la dirección del precio semanal.
>
> Súper · Regular · Diésel
>
> Equipo 06 · ML Engineering · CC3105

Incluir los seis nombres y la fecha de exposición.

**Visual**: una fotografía real de un rótulo o bomba y una secuencia pequeña:
foto → precio estructurado → consulta y predicción.

**Notas para exponer**

“Los precios aparecen en fotografías que no se pueden consultar directamente como
una tabla. Nuestro proyecto los extrae, revisa su calidad y conserva un histórico.
Con datos históricos también estimamos si el precio de cada combustible subirá,
bajará o se mantendrá la siguiente semana.”

**Mensaje principal**: el producto entrega datos y una clasificación semanal;
el modelo vigente no predice un precio exacto en quetzales.

### Diapositiva 2. Tres etapas convierten las fotos en información

**Texto visible**

- **Bronce:** fotos originales, fecha, ubicación y fuentes complementarias.
- **Plata:** lectura del texto, normalización y control de calidad.
- **Oro:** indicadores semanales, modelos y predicciones.
- **API:** consulta del histórico y de los resultados.

**Visual**: diagrama con flechas y pocos rótulos. Usar como recurso editable
[`../docs/arquitectura.drawio`](../docs/arquitectura.drawio) o como referencia
[`../docs/arquitectura.png`](../docs/arquitectura.png).

**Flujo que debe representar la nueva imagen**

```text
Fotos + histórico MEM + WTI + eventos de subsidio
                      ↓
        Databricks: Bronce → Plata → Oro
                      ↓
           SQL warehouse → FastAPI
                      ↓
             Consultas HTTP del usuario

Job: ejecuta Bronce → Plata → Oro
MLflow: conserva experimentos, métricas y modelos
Droplet: API pública en http://159.65.111.14:8000
```

**Notas para exponer**

“Bronce conserva el material original para poder revisar su origen. Plata convierte
las imágenes en precios y separa los registros rechazados. Oro organiza las semanas
y genera los resultados del modelo. La API permite consultarlos sin abrir un notebook.”

**Precisión operativa**: Bronce lee las fotos del bucket del catedrático por la
external location `xloc-raw`. Las tablas son Delta gestionadas en `equipo_06_*` porque
`xloc-cusn/ag/au` siguen de solo lectura; el Job ya recibe las rutas `s3://` por capa
para crearlas como externas en cuanto se habilite la escritura. La API lee Oro con SQL warehouse.

### Diapositiva 3. Conservamos las fotos y medimos con referencias manuales

**Texto visible**

- **110 fotos** oficiales (2023–2026) leídas de S3 a Bronce.
- **36 fotos y 85 precios** con referencia manual para evaluar OCR.
- Histórico de variables: **264 filas**, del **26/11/2024 al 03/11/2026**.
- Precios en **quetzales por galón**; semanas de **martes a lunes**.

**Visual**: tres cifras grandes con sus denominadores y una línea de tiempo.
Identificar por separado “fotos”, “precios etiquetados” y “filas del histórico”.

**Notas para exponer**

“La evaluación de lectura utiliza las etiquetas existentes del equipo: 85 precios
legibles en 36 fotos. Los datos históricos del MEM aportan las observaciones para
el clasificador; las 110 fotos no son por sí solas todo el conjunto de entrenamiento.
Conservamos fecha y ubicación desde EXIF cuando están disponibles y usamos la
carpeta de origen como respaldo para la fecha.”

**Evitar una confusión**: 264 filas de variables no equivalen a 264 semanas.
Tampoco todas tienen objetivo y dirección actual conocidos para la evaluación.

### Diapositiva 4. El OCR acierta 78 de 85 precios etiquetados

**Texto visible**

> **91.8% de acierto** con RapidOCR y gris con CLAHE.

| Preprocesamiento | Correctos / etiquetas | Exactitud |
| --- | --- | --- |
| Gris con CLAHE | 78/85 | 91.8% |
| Gris con CLAHE, tamaño doble | 77/85 | 90.6% |
| Imagen original | 75/85 | 88.2% |
| Binarización | 44/85 | 51.8% |

Pie: evaluación sobre 36 fotos; diferencia absoluta menor que **Q0.005** para
considerar un precio correcto.

**Visual**: barras horizontales de 0 a 100%, ordenadas como la tabla, con la
configuración elegida destacada. Si el gráfico ya contiene las cifras, omitir
la tabla en la diapositiva y conservarla en las notas.

**Notas para exponer**

“Comparamos cuatro formas de preparar la imagen con el mismo motor y las mismas
etiquetas. CLAHE mejora el contraste local. La mejor variante encontró correctamente
78 precios: quedaron seis valores incorrectos y uno sin detectar. Aumentar la
imagen al doble no mejoró el resultado y elevó el consumo de memoria.”

**Datos para ampliar en preguntas**

- Fotos con todas sus etiquetas correctas: 80.6%, 77.8%, 72.2% y 30.6%, respectivamente.
- Mejor variante: diez lecturas adicionales sin etiqueta manual; se reportan aparte.
- Cero salidas duplicadas para las llaves etiquetadas en esa variante.
- El 91.8% mide precios correctos frente a etiquetas; no es accuracy del clasificador,
  confianza del OCR ni porcentaje de fotos totalmente correctas.
- Estas cuatro corridas compararon preprocesamientos de RapidOCR. EasyOCR es una
  opción del código, pero no se debe presentar como un motor evaluado en esta tabla.

### Diapositiva 5. Las reglas separan datos aceptados y rechazados

**Texto visible**

- **221 filas aceptadas** y **26 rechazadas** en Plata.
- Rechazo: **26/247 = 10.5%** de las filas contabilizadas.
- Reglas: combustible válido, rango **Q20–Q60**, fecha y confianza.
- Trazabilidad y carga mediante MERGE para evitar duplicados.

**Visual**: fotografía real recortada junto a referencia y lectura del OCR.
Elegir uno de estos ejemplos comprobados:

| Foto | Combustible | Referencia | Resultado OCR |
| --- | --- | --- | --- |
| IMG_7575.HEIC | Diésel | Q24.89 | Sin detección |
| IMG_8064.HEIC | Regular | Q35.16 | Q35.76 |
| IMG_8636.HEIC | Diésel | Q41.69 | Q47.69 |

**Notas para exponer**

“Dos rechazos fueron por fotos sin precios legibles y uno por confianza inferior al
umbral. Aun así, una lectura incorrecta puede pasar las reglas: Q35.76 sigue siendo
un precio plausible. Por eso medimos tanto aceptación de registros como exactitud
frente a revisión manual. Son controles diferentes.”

La llave de MERGE incluye fecha, ubicación, combustible y modalidad. V-Power se
excluye del catálogo solicitado. El 3.125% corresponde a filas, no al porcentaje de
fotos rechazadas ni a la tasa de error OCR.

### Diapositiva 6. Estimamos la dirección de la siguiente semana

**Texto visible**

> Objetivo: **sube · baja · se mantiene**

- Sube si el cambio es mayor que **Q0.10**.
- Baja si es menor que **−Q0.10**.
- Se mantiene entre **−Q0.10 y Q0.10**, incluidos ambos límites.
- Variables: cambios recientes, promedio de cuatro semanas, combustible y contexto.
- Evaluación temporal: **183 registros de entrenamiento / 30 de prueba**.

**Visual**: una línea de tiempo con entrenamiento a la izquierda y las diez semanas
elegibles de prueba a la derecha. No dibujarlas como diez semanas consecutivas:
hay huecos en el histórico.

**Notas para exponer**

“Usamos cuatro variaciones anteriores, el promedio móvil, la diferencia entre súper
y diésel, el combustible y la dirección actual. WTI y subsidio aportan contexto
cuando hay datos. Los faltantes numéricos se imputan con la mediana calculada solo
en entrenamiento y se agregan indicadores de ausencia. No interpolamos semanas.
Separamos por fecha y mantenemos los combustibles de una misma semana en el mismo
conjunto para evitar mezclar esa semana entre entrenamiento y prueba.”

**Variables exactas para las notas o apéndice**

| Variable | Qué representa / por qué se usa |
| --- | --- |
| var_q_1 a var_q_4 | Cambios previos; describen el comportamiento reciente |
| prom_movil_4 | Nivel medio reciente del precio |
| dif_super_diesel | Diferencia entre combustibles |
| direccion_actual | Estado actual y referencia de persistencia |
| combustible | Identifica súper, regular o diésel; codificación one-hot |
| wti_var_1 | Cambio del petróleo WTI, cuando existe |
| subsidio_activo | Contexto de subsidio, cuando existe |

### Diapositiva 7. La regresión logística supera la base, con límites

**Texto visible**

| Modelo | Accuracy | F1 macro |
| --- | --- | --- |
| Línea base: repetir dirección actual | 50.0% | 0.2564 |
| **Regresión logística, elegida** | **60.0%** | **0.3130** |
| Árbol de decisión | 43.3% | 0.3056 |

> **18/30 aciertos frente a 15/30 de la base.**
>
> La clase “se mantiene” sigue siendo una debilidad.

**Visual**: dos gráficos alineados, uno de accuracy (0–100%) y otro de F1 macro
(0–1). Mantener las mismas posiciones y colores de los modelos. No mezclar las
dos escalas en una sola serie.

**Notas para exponer**

“La base supone que la dirección actual continuará. La regresión logística mejora
la accuracy en diez puntos porcentuales y obtiene el mejor F1 macro entre los
candidatos. Pero el F1 sigue bajo: la prueba tiene 18 subidas, ocho bajadas y solo
cuatro casos de estabilidad, y la logística no acertó esos cuatro casos. Por eso
no basta con reportar el 60%.”

“Elegimos el modelo con esta misma prueba temporal. Eso introduce sesgo de selección:
necesitamos una evaluación futura independiente para estimar mejor su desempeño.
Después de elegirlo, se reentrena con las observaciones elegibles disponibles y se
conserva en MLflow junto con métricas y matrices de confusión.”

**Fuente**: corrida de Oro y tabla `workspace.equipo_06_gold.metricas_modelo`.
No llamar a las probabilidades “certeza” ni presentar la mejora como estadísticamente
significativa: no se realizó ese análisis.

### Diapositiva 8. El Job completó dos cargas verificadas

**Texto visible**

> **Bronce → Plata → Oro: SUCCESS en ambas ejecuciones**

| Validación | Fotos | Rutas distintas | Bronce / Plata / Oro |
| --- | --- | --- | --- |
| Primera | 1 | 1 | 38 / 167 / 139 s |
| Segunda | 2 | 2 | 36 / 144 / 139 s |

- Serverless, entorno **2**.
- Programación: martes **07:00**, Guatemala.
- Alertas de fallo por correo.

Pie: fotos reales existentes; esquemas separados de producción; `modo=batch_merge`.
Los tiempos de tareas excluyen aprovisionamiento y esperas.

**Visual**: captura real del historial con las tres tareas en verde, acompañada
del conteo 1 → 2. Obtenerla desde los enlaces de evidencia del apartado 5.
Si no se cuenta con captura, usar la tabla y los enlaces verificables.

**Notas para exponer**

“La segunda ejecución incorporó una foto adicional de otra semana y conservó las
rutas únicas. Estas validaciones se hicieron con fotos reales ya existentes, en
esquemas separados, mediante MERGE. No equivalen a haber observado una ejecución
programada ni a probar Auto Loader en producción. Un intento inicial falló por
dependencias del entorno; fijar la versión compatible permitió completar ambos.”

“MLflow conserva los experimentos. En local aprobaron 143 pruebas y una se omitió
por ausencia de PySpark; los notebooks también se ejecutaron en Databricks.”

No presentar estos tiempos como costo monetario, latencia de API ni duración total
exacta del Job. No afirmar que existen clusters clásicos: el cómputo utilizado es
serverless. El Job actual usa copias del Workspace; un push a Git no las sincroniza
automáticamente.

### Diapositiva 9. Los resultados se consultan desde una API

**Texto visible**

- Precios actuales e histórico.
- Predicción por combustible.
- Métricas del modelo frente a la base.
- Siete consultas locales contra tablas reales: **HTTP 200**.

| Combustible | Semana objetivo | Dirección | Probabilidad del modelo |
| --- | --- | --- | --- |
| Súper | 10/11/2026 | Baja | 0.8139 |
| Regular | 10/11/2026 | Baja | 0.8613 |
| Diésel | 10/11/2026 | Baja | 0.8908 |

**Visual**: una respuesta real de `/prediccion` y un QR a
`http://159.65.111.14:8000/docs`. Probar ese destino desde un teléfono antes de
publicar la presentación. Se puede cambiar el destino a la consulta directa
`http://159.65.111.14:8000/prediccion?combustible=super` si resulta más claro.

**Estado al corte**: API pública en `http://159.65.111.14:8000`, `/health` con `fuente_oro=databricks`.
Mantener ese aviso hasta comprobar acceso externo. Los siete HTTP 200 fueron
pruebas locales de FastAPI conectadas a las tablas reales de Databricks.

**Notas para exponer**

“La API entrega precios, predicciones y métricas mediante consultas HTTP. La última
semana del histórico comienza el 3 de noviembre; por eso la salida disponible tiene
como objetivo el 10. Esa fecha se calcula desde los datos, no desde la fecha del
equipo. Las probabilidades son salidas del modelo y no garantías de acierto.”

La tabla muestra predicciones generadas, no resultados posteriormente acertados.
No hay datos del 10 de noviembre para evaluar esas predicciones o avanzar a la
semana del 17. No cambiar solamente la fecha en la diapositiva o en la respuesta.

### Diapositiva 10. Qué aprendimos y qué sigue

**Texto visible**

- El OCR requiere etiquetas y revisión: **91.8% de acierto**.
- La evaluación temporal permite comparar con una base: **60% vs. 50%**.
- La trazabilidad ayuda a revisar errores y reproducir ejecuciones.
- Próximos pasos: mejorar estabilidad, evaluar semanas futuras y cerrar el despliegue.

**Visual**: tres conclusiones breves y una transición a la demostración.

**Notas para exponer**

“Construimos y verificamos el recorrido desde fotos hasta resultados consultables.
Los límites principales siguen siendo los errores de lectura y la baja cobertura
de estabilidad del clasificador. El siguiente paso es reunir más observaciones,
evaluar semanas futuras e incorporar la semana del 10 de noviembre para predecir el 17.”

## 3. Demostración de cinco minutos

### Preparación antes de exponer

- Ariela: actualizar el servidor con [la guía de despliegue](../docs/DESPLIEGUE.md).
- Comprobar el servicio desde otra red y verificar `fuente_oro=databricks` en `/health`.
- Abrir previamente Job, historial, tablas necesarias y documentación `/docs`.
- Comprobar el QR con el teléfono. No publicar tokens ni archivos `.env` en pantalla.
- Preparar fotos reales y rutas aisladas para la demo; no alterar producción para ensayar.
- Tener capturas reales o una grabación breve como respaldo. Aún no se generó una
  grabación en la entrega anterior.

### Secuencia y tiempos

| Tiempo | Acción | Evidencia que se explica |
| --- | --- | --- |
| 0:00–0:45 | Mostrar foto adicional y ejecutar el Job con parámetros revisados | Origen y trazabilidad de la entrada |
| 0:45–1:30 | Mostrar dependencia Bronce → Plata → Oro e historial previo | Orquestación y dos ejecuciones exitosas |
| 1:30–2:15 | Consultar `/health` y `/precios/actual` | Fuente real y precios por combustible |
| 2:15–3:30 | Consultar `/prediccion` y escanear QR | Combustible, fecha objetivo, dirección y probabilidad |
| 3:30–4:15 | Consultar `/modelo/metricas` | Modelo elegido y línea base |
| 4:15–5:00 | Revisar avance del Job y cerrar con evidencia disponible | Conteos y estado real de la ejecución |

Las tareas medidas sumaron más de cinco minutos, sin incluir esperas. Por ello,
iniciar el Job al principio y mostrar resultados previos verificables mientras
corre. Si no termina durante la demo, indicar que sigue en curso. No presentar una
captura previa como resultado de la ejecución recién lanzada.

### Consultas listas para usar

Abrir en navegador, o ejecutar lo siguiente en Bash:

```bash
BASE_URL=http://159.65.111.14:8000
curl --fail --max-time 30 "$BASE_URL/health"
curl --fail --max-time 30 "$BASE_URL/precios/actual"
curl --fail --max-time 30 "$BASE_URL/prediccion?combustible=super"
curl --fail --max-time 30 "$BASE_URL/prediccion?combustible=regular"
curl --fail --max-time 30 "$BASE_URL/prediccion?combustible=diesel"
curl --fail --max-time 30 "$BASE_URL/precios?combustible=diesel&desde=2026-10-01&hasta=2026-11-30&limit=10"
curl --fail --max-time 30 "$BASE_URL/modelo/metricas"
```

La suite equivalente está en [tests/consultas_api.sh](../tests/consultas_api.sh):

```bash
BASE_URL=http://159.65.111.14:8000 bash tests/consultas_api.sh
```

### Plan B

Si falla la red o el servidor, mostrar respuestas y capturas previamente guardadas,
identificadas con fecha y origen. Si solo se tiene la prueba local con datos reales,
explicar ese alcance. No cambiar a datos de demostración y presentarlos como producción.

## 4. Preguntas probables del jurado

**¿Por qué no basta con leer los números de la foto?**

También hay que asociarlos al combustible correcto, identificar fecha y modalidad,
normalizar el importe y controlar lecturas equivocadas. Pantallas de siete segmentos,
reflejos y rótulos verticales pueden confundir dígitos.

**¿Cómo calcularon el 91.8%?**

78 precios correctos divididos entre 85 referencias manuales. Se exige diferencia
absoluta menor que Q0.005. Es una medición distinta de la confianza interna del OCR.

**¿Rechazar solo 3.125% significa que el resto está correcto?**

No. Las reglas detectan valores no válidos o dudosos, pero algunos errores siguen
siendo plausibles. Por eso hay una evaluación manual independiente.

**¿Por qué el modelo tiene 60% si el OCR tiene 91.8%?**

Son tareas y denominadores distintos: leer un precio frente a estimar una dirección
futura. No deben interpretarse como métricas intercambiables.

**¿Qué hace la línea base?**

Repite la dirección actual para la semana siguiente. Permite medir si un modelo
aporta algo frente a esa regla sencilla.

**¿Por qué reportan F1 macro?**

Da el mismo peso a cada clase. La accuracy puede ocultar un mal desempeño en la
clase menos representada. La logística no acertó casos de estabilidad en esta prueba.

**¿Hay fuga de información?**

La separación es temporal y por semana, y la imputación se ajusta en entrenamiento.
Sin embargo, se eligió el modelo usando la misma prueba que se reporta: existe
sesgo de selección y hace falta una evaluación futura independiente.

**¿Las diez semanas de prueba son consecutivas?**

No. Son las últimas diez semanas elegibles con objetivo y dirección actual
conocidos; hay huecos. Incluyen 30 registros, tres combustibles por semana.

**¿Por qué la predicción es del 10 de noviembre?**

El histórico termina en la semana del 3 de noviembre. El modelo calcula la semana
siguiente desde esa fecha. No se dispone de datos del 10 para avanzar al 17.

**¿La probabilidad de 0.89 significa 89% de certeza?**

Es la probabilidad asignada por el modelo a la clase elegida. No garantiza que ese
evento ocurra y no se ha demostrado calibración de probabilidades en esta entrega.

**¿El Job ya se ejecutó automáticamente por horario?**

El horario está configurado, pero las dos ejecuciones documentadas fueron lanzadas
para validación con rutas y esquemas aislados, mediante `batch_merge`.

**¿Dónde están las tablas y por qué no leen directamente de S3?**

Las fotos sí se leen de S3, por la external location `xloc-raw`. Las tablas son
gestionadas porque las external locations de escritura (`xloc-cusn/ag/au`) siguen
marcadas como solo lectura; el Job ya acepta las rutas `s3://` de cada capa. La API
consulta Oro por SQL warehouse, alternativa aprobada por el catedrático el 13 de noviembre.

**¿Qué ocurre si el pipeline falla?**

Las tareas dependientes quedan sin ejecutarse y se envía alerta a los correos
configurados. El intento fallido inicial de Silver produjo un correo; tras corregir
el entorno, ambas validaciones terminaron correctamente.

**¿Cuánto cuesta ejecutarlo?**

Se midieron tiempos de tareas, pero no consumo monetario real. No se puede derivar
un costo solo de esos tiempos ni inventar nodos o workers en serverless.

## 5. Recursos y evidencias para construir la presentación

### Recursos del repositorio

| Recurso | Uso |
| --- | --- |
| [Informe editable](../docs/informe.md) | Explicación técnica completa |
| [Informe PDF](../docs/informe.pdf) | Versión de cinco páginas |
| [Arquitectura PNG](../docs/arquitectura.png) | Referencia visual; ajustar almacenamiento al estado real |
| [Arquitectura draw.io](../docs/arquitectura.drawio) | Fuente editable del diagrama |
| [Cierre de Modelos](../docs/modelos/CIERRE_MODELOS.md) | Métricas, metodología y reproducción |
| [Evidencias del Job](../docs/evidencias_job.md) | Alcance, ejecuciones, conteos y corrección del fallo |
| [Datos del Job](../docs/evidencias_job.json) | Cifras estructuradas para tablas y gráficos |
| [Nota de cómputo](../docs/nota_clusters.md) | Entorno serverless y diferencias frente a clusters clásicos |
| [Guía SSH](../docs/DESPLIEGUE.md) | Actualización y comprobación del servidor |
| [Instructivo general, sección 11.3](../docs/instructivos/INSTRUCTIVO_GENERAL.md) | Orden, tiempos y requisitos del jurado |

### Enlaces de Databricks

Requieren acceso autorizado al workspace; no sustituyen un enlace público para el jurado.

- [Primera corrida completa, SUCCESS](https://dbc-f51e9943-f137.cloud.databricks.com/?o=1420684327351409#job/637916192930332/run/337245597755365).
- [Segunda corrida completa, SUCCESS](https://dbc-f51e9943-f137.cloud.databricks.com/?o=1420684327351409#job/637916192930332/run/417806436744272).
- [Oro productivo y modelos, SUCCESS](https://dbc-f51e9943-f137.cloud.databricks.com/?o=1420684327351409#job/179065592137118/run/31229731884243).
- [Comparación OCR, SUCCESS](https://dbc-f51e9943-f137.cloud.databricks.com/?o=1420684327351409#job/640585771730337/run/555603084915275).

Las fotos originales están en `s3://cc3105-raw-869227452861-us-east-2-an/img/` (external location `xloc-raw`).
El CSV de referencia está en `/Volumes/workspace/equipo6_bronze/crudos/etiquetas.csv`.
Desde Databricks se pueden descargar recortes para la presentación. No inventar
imágenes de evidencia ni incluir datos privados innecesarios al tomar capturas.

Los CSV de OCR y respaldos descargados se conservaron localmente en
`artifacts/databricks/experimentos_ocr/`. Esa carpeta está ignorada por Git:
si otra persona necesita los archivos originales, enviárselos por separado o
descargarlos desde las corridas. Este Markdown ya contiene las cifras necesarias
para recrear los gráficos principales.

## 6. Qué actualizar antes de entregar

| Punto | Estado verificado al 15/11/2026 | Acción previa a exponer |
| --- | --- | --- |
| OCR y modelos | Corridas reales completadas | Conservar cifras o reemplazar solo con nueva evidencia |
| Job | Dos validaciones completas SUCCESS | Preparar historial y ensayo de demo |
| API con datos reales | Pública en :8000, `fuente_oro=databricks` | Volver a comprobar el día de la presentación |
| URL y QR | `http://159.65.111.14:8000/docs` responde | Probar desde un teléfono |
| S3 externo | Fotos leídas por `xloc-raw`; escritura en `xloc-cusn/ag/au` aún de solo lectura (16/11) | Si el catedrático la habilita, llenar las rutas `s3://` del Job |
| Predicción | Objetivo 10/11/2026 | Mantener la fecha mientras no cambie el histórico |
| Capturas y grabación | Enlaces de evidencia disponibles; grabación no creada | Guardar material de respaldo real |
| Exposición | Reparto sugerido | Ajustar responsables y ensayar los diez minutos |

El resumen de una página debe entregarse **48 horas antes** según el instructivo.
Actualizarlo junto con la presentación si cambia el despliegue, la URL o las métricas.

## 7. Instrucción lista para otra herramienta de presentaciones

Copiar este bloque y adjuntar este Markdown; agregar las fotos reales y el diagrama
si se desea utilizarlos. Las cifras ya están incluidas en el documento.

```text
Crea una presentación editable en español para un jurado que no conoce el curso.
Utiliza como fuente el documento adjunto CONTENIDO_PRESENTACION.md.

Entrega diez diapositivas para diez minutos de exposición, con notas de orador.
Reserva por separado cinco minutos para demo y cinco para preguntas.
Sigue el orden y los contenidos de las diapositivas 1 a 10 del documento.
Usa formato 16:9, texto breve, títulos claros, gráficos legibles y diagramas simples.
La propuesta visual puede ser nueva; no hace falta reproducir la presentación anterior.

Incluye los seis integrantes y permite ajustar el reparto de exposición.
Presenta OCR y clasificación como evaluaciones distintas, con sus denominadores.
Usa los valores exactos de las tablas para gráficos y conserva las notas de limitaciones.
La predicción disponible corresponde al 10 de noviembre de 2026.
La API está publicada en http://159.65.111.14:8000 y el catedrático aprobó la lectura
de Oro por SQL warehouse.
No inventes resultados, capturas, matrices de confusión, costos ni un despliegue exitoso.
El QR apunta a http://159.65.111.14:8000/docs.
Las preguntas probables y los detalles de implementación van en notas o apéndice,
no como párrafos extensos en las diez diapositivas principales.
```
