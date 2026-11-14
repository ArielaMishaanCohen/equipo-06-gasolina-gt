# Persona 1 Extracción de precios en Databricks

Tu entrega conecta el OCR que ya existe con las fotos de Bronce, muestra su exactitud y deja
los precios listos para las reglas de calidad. El trabajo se hace en la rama `modelos-extraccion`.
El clasificador de predicción y los experimentos de OCR corresponden a otras partes del equipo.

## 1 Antes de entrar a Databricks

Los archivos de tu entrega son:

- `pipelines/02_silver.py`: instalación, prueba del motor en driver y worker, extracción
  incremental con `mapInPandas`, DataFrame `candidatos` y tablas de exactitud.
- `src/gasolina/silver_extraccion.py`: adaptación de bytes a OCR y preparación de resultados.
- `tests/test_silver_extraccion.py`: pruebas de integración con OCR simulado.

Pide al equipo de Datos confirmar que `00_setup.sql` y `01_bronze.py` ya corrieron, que
`workspace.equipo6_bronze.fotos_precios` tiene fotos y que tienes permiso de escritura en Plata.
Usa esos nombres, que son los del código y configuración actuales; algunas guías antiguas
escriben `equipo_06`, pero ese no es el valor predeterminado actual.

Pide a Persona 2 la ruta de **su CSV revisado** de etiquetas en S3 o en un Volume. El notebook
requiere `foto`, `combustible` y `precio_q_galon`; admite las columnas adicionales del contrato.
No subas las fotos ni las etiquetas al repositorio. Se necesitan al menos 20 fotos etiquetadas
presentes en Bronce para completar la revisión exigida.

## 2 Subir tu rama a GitHub

En una terminal de PowerShell abierta en esta carpeta, comprueba primero los cambios:

```powershell
git branch --show-current
git diff --stat
git status --short
```

La rama debe ser `modelos-extraccion`. Para registrar y subir tu entrega:

```powershell
git add pipelines/02_silver.py src/gasolina/silver_extraccion.py tests/test_silver_extraccion.py docs/instructivos/PERSONA_1_DATABRICKS.md
git commit -m "modelos: integrar extraccion OCR en Silver y evaluar exactitud"
git push -u origin modelos-extraccion
```

Estos comandos todavía debes ejecutarlos tú: los cambios quedan locales hasta el commit y push.

## 3 Abrir el proyecto en Databricks

1. Entra al workspace de Databricks del curso.
2. En **Workspace**, abre tu carpeta y crea una **Git folder** si no tienes el repo.
   Usa `https://github.com/ArielaMishaanCohen/equipo-06-gasolina-gt.git`.
3. Selecciona la rama `modelos-extraccion` y actualiza con **Pull** si ya tenías el repo.
4. Dentro del repo abre `pipelines/02_silver.py` como notebook.
5. Conéctalo al compute del curso que permita Python y `mapInPandas`. Usa el runtime
   compatible que haya configurado el equipo de Datos; no uses un SQL warehouse para este notebook.

## 4 Instalar y comprobar las librerías

Ejecuta la primera celda `%pip install ..`: instala el paquete desde la raíz del Git folder,
un nivel arriba de `pipelines`. Si no encuentra `pyproject.toml`, reemplaza esa celda con tu
ruta real, entre comillas si contiene espacios:

```python
%pip install "/Workspace/Users/TU_CORREO/equipo-06-gasolina-gt"
```

Después ejecuta la celda `dbutils.library.restartPython()`, que reinicia el intérprete.
Es el procedimiento documentado por [Databricks para librerías del notebook](https://docs.databricks.com/aws/en/libraries/notebooks-python-libraries).
Las dependencias `rapidocr_onnxruntime==1.3.24` y `pillow-heif` ya están declaradas en
`pyproject.toml`; no necesitas modificar ese archivo ni instalar EasyOCR para esta entrega.

Al avanzar en el notebook verás la tabla `entorno / versiones` para `driver` y `worker`.
Cada uno abre el motor y ejecuta OCR sobre una imagen blanca de prueba. Guarda una captura:
esa salida demuestra que las librerías se importan y el motor inicia en el compute usado.
La comprobación del worker prueba una tarea de Spark; la extracción posterior usa los workers
que Spark asigne. Un error de librerías detiene la ejecución para que no se registre como foto ilegible.

## 5 Configurar los parámetros

Ejecuta la celda que crea widgets. En la parte superior del notebook configura:

| Widget | Valor inicial |
| --- | --- |
| `catalogo` | `workspace` |
| `esquema_bronze` | `equipo6_bronze` |
| `esquema_silver` | `equipo6_silver` |
| `motor` | `rapidocr` |
| `preproc` | `gris_clahe` |
| `reprocesar` | `false` |
| `ruta_etiquetas` | Ruta completa al `etiquetas.csv` revisado por Persona 2 |
| `ruta_reporte_exactitud` | Carpeta de salida en S3 o Volume donde tengas permiso de escritura |
| `ruta_equipo_silver` | `s3://cc3105-ag-869227452861-us-east-2-an/equipo6` |

El último widget aparece al ejecutar la sección 2. La carpeta para reportes puede ser,
por ejemplo, `s3://cc3105-ag-869227452861-us-east-2-an/equipo6/reportes/exactitud_persona1`.
Se escriben las subcarpetas `resumen/` y `por_foto/`, cada una con un `part-*.csv` y archivos
auxiliares de Spark. Volver a usar la misma carpeta reemplaza ese reporte; usa otra carpeta
si quieres conservar una corrida anterior.

Si aún no tienes etiquetas, deja esa ruta vacía: el notebook mostrará la evaluación como
pendiente y sí permitirá extraer y cargar los precios. Para completar la entrega tendrás que
volver a correrlo con el CSV. No se da por comprobado el 91.8 % mencionado en el mensaje del equipo:
el porcentaje que debes reportar es el calculado con tu CSV y tus parámetros.

## 6 Ejecutar y revisar los resultados

Ejecuta las celdas restantes en orden. Después de cambiar widgets vuelve a ejecutar la celda
que lee sus valores y las siguientes. En una ejecución completa verás:

1. Prueba de librerías y motor en driver y worker.
2. Número de fotos pendientes. Las que ya están en `precios` o `precios_rejected`, con la
   versión del paquete y motor actuales, se omiten con `reprocesar=false`.
3. `candidatos`: una fila por combustible con fecha EXIF, o de carpeta si falta EXIF, precio,
   modalidad, ubicación, ruta de foto, confianza, motor y versión. Las ausencias de modalidad
   y ubicación se convierten a `no_indica`. Sin fecha, la fila irá a revisión por calidad.
4. Tabla global y tabla por foto de exactitud. Se cuentan aciertos, incorrectos y precios
   no encontrados; un acierto exige una diferencia menor de Q0.005. Las lecturas adicionales
   sin etiqueta manual aparecen como `sin_etiqueta`, separadas de los errores medidos.
5. Bloque de Datos: aplicación de calidad, carga de `precios`, cuarentena y referencia del MEM.
6. Mensaje de idempotencia: al repetir la carga con los mismos datos, los conteos no cambian.

Si todas las fotos ya estaban procesadas, puede haber cero candidatos nuevos y aun así
mostrarse la evaluación: se vuelven a leer las fotos etiquetadas para medir el OCR actual.
La evaluación usa la extracción antes del filtro de calidad, por lo que su número de precios
puede diferir del número final en `precios`.

Una foto sin precios se representa con combustible y precio nulos; el bloque de calidad la
guarda en `precios_rejected` con regla y motivo `sin_precios_legibles`.

## 7 Comprobar las tablas y guardar evidencia

En una nueva celda SQL del notebook ejecuta:

```sql
%sql
SELECT COUNT(*) AS fotos FROM workspace.equipo6_bronze.fotos_precios;

SELECT combustible, COUNT(*) AS lecturas
FROM workspace.equipo6_silver.precios GROUP BY combustible;

SELECT regla, motivo, COUNT(*) AS rechazos
FROM workspace.equipo6_silver.precios_rejected GROUP BY regla, motivo;

SELECT * FROM workspace.equipo6_silver.precios ORDER BY fecha DESC LIMIT 20;
```

Vuelve a correr el notebook con `reprocesar=false`. Si no llegaron fotos nuevas y no cambió
la versión o motor, las fotos ya registradas en Plata no se vuelven a extraer para la carga.
Comprueba que los conteos de precios y rechazos se mantienen. La evaluación sí puede ejecutar
OCR de nuevo para producir la tabla completa.

Conserva capturas de dependencias, candidatos, exactitud global y por foto, resumen de Plata
y segunda ejecución. Conserva también los CSV del reporte y anota motor, preproc y versión.
La tabla de exactitud debe incluir al menos 20 fotos realmente evaluadas y cero fotos ausentes;
si no, coordina con Datos y Persona 2 antes de presentar el resultado como revisión completa.

## 8 Abrir el pull request

Después del push y la prueba en Databricks, abre en GitHub un pull request desde
`modelos-extraccion` hacia `main`. Describe la extracción, adjunta la evidencia y el porcentaje
real medido, y pide la revisión de otro integrante antes del merge, como acordó el equipo.
Puedes usar este texto y completar los espacios:

> Integra Bronce con el OCR mediante mapInPandas y deja candidatos para calidad y MERGE.
> Verifica el motor en driver y worker y muestra exactitud global y por foto.
> Validación en Databricks: ___ fotos, ___ precios etiquetados, ___ % de precios correctos.
> Segunda ejecución: ___ fotos pendientes; conteos de Plata sin duplicados.

## Soluciones a errores frecuentes

| Mensaje o situación | Qué hacer |
| --- | --- |
| No existe una tabla | Coordina con Datos para ejecutar setup e ingesta; revisa los widgets de catálogo y esquemas. |
| `No module named gasolina` | Revisa la ruta del `%pip install`, instala desde la raíz del repo y reinicia Python. |
| Falla la instalación o importación de ONNX/HEIF | Conserva el error completo y compártelo con Datos/Producción; verifica el runtime y acceso a paquetes. No cambies versiones al azar. |
| No hay permisos de S3 o de tabla | Pide al equipo verificar los permisos de Unity Catalog y external locations; no pongas credenciales en el código. |
| La tabla de exactitud dice pendiente | Configura `ruta_etiquetas` y ejecuta otra vez. |
| Foto etiquetada ausente | Comprueba su nombre en Bronce y en el CSV; no se sustituye por otra foto. |
| Nombre de foto ambiguo o etiqueta duplicada | Coordina la corrección del CSV o los nombres con Persona 2/Datos antes de medir. |
| Cambiaste preproc y no hay fotos pendientes | Usa `reprocesar=true` para repetir OCR y carga; al terminar vuelve a `false`. |

`reprocesar=true` usa el MERGE existente de Datos: actualiza llaves coincidentes, pero no
elimina automáticamente precios antiguos cuya fecha, ubicación, modalidad o combustible
cambien. Si cambian esas llaves, coordina la reconciliación con Datos antes de usarlo sobre
resultados definitivos.
