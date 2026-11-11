# Guía de rol: Modelos (v3)

Proyecto Final ML Engineering · Equipo 06 (confirmar) · Responsable: ________

Esta guía es tu lista de tareas en orden, con los prompts completos. El mapa del proyecto está en `INSTRUCTIVO_GENERAL.md` v3: léete al menos las secciones 0, 1, 3 y 5 (20 minutos). Tu trabajo vale la extracción de Plata (la mayor parte de 15 puntos) y el modelo de predicción (10), y define los puntos extra por la mejor predicción de la semana 5.

---

## 1. Tu rol en una tabla

| Qué | Detalle |
| --- | --- |
| Entregas | `extraer_precios` (OCR + reglas) para fotos genéricas; la parte de extracción de `02_silver`; revisión manual de 20+ fotos con % de aciertos; experimentos de OCR en MLflow; clasificador `sube`/`baja`/`se_mantiene` frente a la línea base; `gold.predicciones` y `gold.metricas_modelo`. |
| Dependes de | Datos: `bronze.fotos_precios` (semana 1) y `gold.features_modelo` (semana 3). |
| Dependen de ti | Datos necesita `extraer_precios` real en la semana 2 para llenar `silver.precios`. La API lee tus tablas de predicción y métricas. |
| Tus archivos | `src/gasolina/metadata.py`, `ocr.py`, `reglas.py`, `extraccion.py`, `modelo.py`, la parte de extracción de `pipelines/02_silver.py`, la parte de modelo de `pipelines/03_gold.py`, `pipelines/04_experimentos_ocr.py`, sus tests |
| Tu rama | `modelos` |
| No toques | `api/`, `scripts/`, `.github/` (Producción) ni `calidad.py`, `features.py`, `01_bronze.py` (Datos). Cambios en `pyproject.toml` o `config.yaml`: pídeselos a Ariela. |

Hitos:

**Se entrega la próxima semana** (confirmar el día; el plan supone el martes 17). Ya hay permisos para leer las fotos. "Semana 1 … 5" en esta guía son bloques de días:

| Bloque | Cuándo | Qué tiene que existir |
| --- | --- | --- |
| Semana 1 | Mar 10 (noche) – Mié 11 | Fotos del catedrático revisadas y clasificadas por tipo; plantilla `etiquetas.csv` con 20+ fotos; OCR probado. |
| Semana 2 | Mié 11 – Jue 12 | `extraer_precios` real (contrato 5.2) en `main`; `02_silver` llenando `silver.precios`; exactitud medida en 20+ fotos. |
| Semana 3 | Vie 13 – Sáb 14 | Clasificador y línea base con validación temporal en MLflow; `gold.predicciones` y `gold.metricas_modelo`. |
| Semana 5 | Dom 15 – Lun 16 | Informe (extracción y modelo); predicción de la semana siguiente registrada (puntos extra). |

Contratos que te tocan: 5.2 (lo que devuelve `extraer_precios`), 5.3 (`silver.precios`), 5.4 (`gold.features_modelo`, `gold.predicciones`, `gold.metricas_modelo`).

---

## 2. Preparación

### 2.1 Tu Mac 💻

```bash
cd "<tu carpeta del proyecto>"     # aquí también va datos/ con fotos y etiquetas.csv
git clone https://github.com/ArielaMishaanCohen/equipo-06-gasolina-gt.git
cd equipo-06-gasolina-gt
git checkout modelos
python3.11 -m venv .venv && source .venv/bin/activate
pip install -e ".[api,dev]"
pytest
```

Si sale `No module named 'gasolina'` en una Mac, corre `chflags -R nohidden .venv`.

### 2.2 Git folder en Databricks 🧱

Workspace → tu carpeta → Create → Git folder → URL del repo → rama `modelos`. Haz commits desde ahí también: la rúbrica cuenta los commits de cada integrante.

### 2.3 Rutina de Git

```bash
git checkout main && git pull && git checkout modelos && git merge main
# ... trabajas ...
git add -A && git commit -m "modelos: <qué hiciste>" && git push
```

---

## 3. Semana 1 — Preparar la extracción

### 3.1 ⭐ Conocer las fotos

Las fotos oficiales están en `s3://cc3105-raw-869227452861-us-east-2-an/img/` (external location `xloc-raw`, solo lectura). Ariela ya las descargó: pídele `datos/fotos_profesor/` (38 `.HEIC`). Lo que ya sabemos:

- Son **38 fotos de bombas**, aproximadamente una por semana, del 7 de enero al 8 de noviembre de 2026, todas con fecha y GPS en el EXIF.
- Hay **al menos dos marcas**: Puma (pantallitas "ION Diesel", "Regular", "Super") y Shell ("V-Power", "Super", "Regular", "Diesel"), y **el orden de los combustibles cambia entre bombas**. Por eso los precios se asignan por la **etiqueta impresa** más cercana a cada pantallita, nunca solo por la posición.
- V-Power se lee, pero se descarta (el enunciado solo pide super, regular y diésel).
- La pantalla "Esta Venta" (total ÷ galones) sirve para verificar uno de los precios: 100.00 ÷ 3.664 = 27.29 = Super en la foto de Puma.

Antes de programar, abre las 38 en Vista Previa y anota en `etiquetas.csv` la marca y los 3 precios de cada una: es la revisión manual que pide el enunciado (20+ fotos).

### 3.2 ⭐ Plantilla de revisión manual

El enunciado exige revisar a mano **al menos 20 fotos** y reportar el % de precios extraídos correctamente. Crea `datos/etiquetas.csv` (fuera del repo, y también en `s3://cc3105-cusn-…/equipo-06/complementarias/etiquetas/`):

```csv
foto,fecha,combustible,modalidad,ubicacion,precio_q_galon
2026-11-10/IMG_0001.jpg,2026-11-10,super,autoservicio,Shell Km 14,33.45
```

Una fila por precio visible en la foto. Si no se lee ni a simple vista, no se anota y se documenta como limitación.

---

## 4. Semana 2 — Extracción real

### 4.1 ⭐ Metadata

```
PROMPT PARA CLAUDE CODE
Implementa src/gasolina/metadata.py: leer_metadata(ruta) -> dict con exactamente las claves
de "metadata" del contrato 5.2 de docs/instructivos/INSTRUCTIVO_GENERAL.md: archivo,
fecha_hora (ISO, de DateTimeOriginal o DateTime), lat y lon (decimales con signo desde el EXIF
GPS), altitud, modelo_camara, ancho, alto y sha256. Soporta JPG, PNG y HEIC (pillow_heif). Si
falta un campo: None, nunca excepción. Agrega leer_metadata_bytes(contenido, nombre) para
usarla con la columna content de bronze.fotos_precios. Tests con ../datos/IMG_8271.jpg (skip
si no existe).
```

### 4.2 ⭐ OCR + reglas para fotos genéricas

```
PROMPT PARA CLAUDE CODE
Implementa ocr.py, reglas.py y extraccion.py para extraer precios de combustible de fotos
genéricas de Guatemala: rótulos de gasolineras, pantallas de bombas y tablas de precios de
referencia del MEM. El resultado de extraer_precios(ruta_o_bytes, motor="rapidocr",
preproc="gris_clahe") debe respetar EXACTAMENTE el contrato 5.2 de
docs/instructivos/INSTRUCTIVO_GENERAL.md (lista "registros" con combustible, precio_q_galon,
modalidad, ubicacion, confianza y texto_fuente). No toques api/, scripts/ ni calidad.py.
- ocr.py: OcrEngine base; RapidOcrEngine (rapidocr_onnxruntime); EasyOcrEngine con import
  perezoso; preprocesamientos "ninguno", "gris_clahe", "gris_clahe_x2", "binarizado"; reducir
  a ~1600 px de alto.
- reglas.py: normalizar_numero ("33,45" -> 33.45; "3345" -> 33.45; "Q33.45" -> 33.45);
  detectar palabras clave de combustible (super/súper/premium, regular, diesel/diésel/ACPM,
  y variantes con errores de OCR) y de modalidad (autoservicio, servicio completo); asociar
  cada precio a la palabra clave más cercana en la misma fila o justo encima/debajo (usando
  las bbox); clasificar tipo_foto. Para fotos de bomba sin palabras clave, ordenar las
  pantallitas por x como en la v2.
- Validaciones con {nombre, estado: ok|falla|advertencia, mensaje}; score_confianza 0-1.
- Fecha: del EXIF; si no hay, la de la carpeta AAAA-MM-DD (parámetro fecha_carpeta).
- Tests unitarios de reglas.py con detecciones sintéticas (sin imágenes).
Luego crea el CLI gasolina-evaluar --etiquetas datos/etiquetas.csv --imagenes datos/ que
reporte, por foto y global, el % de precios correctos (|pred - real| < 0.005), los precios
no encontrados y los falsos positivos. Corre las combinaciones de preprocesamiento y
muéstrame una tabla.
```

Si la exactitud es baja con rótulos, prueben: recortar la zona de los números antes de una segunda pasada, ampliar 2–3x, o (si el workspace lo permite) un modelo de visión con `ai_query` como experimento comparativo en MLflow.

### 4.3 ⭐ Extracción en `02_silver` 🧱

```
PROMPT PARA CLAUDE CODE
Implementa la parte de extracción de pipelines/02_silver.py (notebook de Databricks) según
la Fase 2 del enunciado y el contrato 5.3: leer de bronze.fotos_precios solo las fotos que no
estén procesadas con la version_modelo actual; aplicar extraer_precios a la columna content
con una pandas UDF (o mapInPandas); explotar "registros" a una fila por combustible con
fecha, combustible, precio_q_galon, modalidad, ubicacion (no_indica si falta), foto_origen,
confianza, motor y version_modelo. Fotos sin registros van a la cuarentena con
motivo "sin_precios_legibles". Deja un DataFrame "candidatos" listo para que la parte de
Datos (calidad.py + MERGE) lo use al final del notebook. Widgets para catálogo, esquemas,
motor y preproc.
```

### 4.4 ⭐ Exactitud de la revisión manual

Corre `gasolina-evaluar` sobre las 20+ fotos etiquetadas y guarda la tabla: es un resultado obligatorio del informe y del notebook de Plata (muéstrala también en `02_silver`).

### 4.5 Experimentos de OCR en MLflow (recomendado)

```
PROMPT PARA CLAUDE CODE
Crea pipelines/04_experimentos_ocr.py (notebook de Databricks): con las fotos de bronce y
etiquetas.csv, una corrida de MLflow por combinación de motor (rapidocr, easyocr si se puede
instalar) y preproc, con métricas pct_precios_correctos, pct_fotos_completas, falsos_positivos
y tiempo_ms_promedio, y como artifact un CSV por foto. Al final, tabla comparativa y el
ganador escrito en config (motor y preproc que usará 02_silver).
```

---

## 5. Semana 3 — Modelo de predicción

### 5.1 ⭐ Clasificador frente a la línea base

```
PROMPT PARA CLAUDE CODE
Implementa src/gasolina/modelo.py y la parte de modelo de pipelines/03_gold.py según la
Fase 3 del enunciado y el contrato 5.4 del instructivo general, usando gold.features_modelo:
1. Objetivo: direccion_siguiente (sube, baja, se_mantiene) por combustible.
2. Validación temporal (walk-forward o las últimas 8-10 semanas como prueba), NUNCA aleatoria.
3. Modelos: línea base ("se repite la dirección de la semana anterior"), regresión logística
   y árbol de decisión (sklearn), con un modelo global y one-hot del combustible.
4. MLflow (experimento /Users/<correo>/equipo06_direccion): una corrida por modelo con
   parámetros, accuracy, F1 macro, matriz de confusión (png) y comparación contra la línea
   base. Registrar el elegido en Unity Catalog si hay permiso; si no, como modelo de MLflow.
5. Si ningún modelo supera a la línea base, se elige la línea base y se documenta (es un
   resultado válido).
6. Escribir gold.predicciones (predicción de la semana siguiente con probabilidad y
   prediccion_baseline; actualizar direccion_real de semanas pasadas) y gold.metricas_modelo,
   con COMMENT en tablas y columnas.
Tests de modelo.py con datos sintéticos.
```

Ojo con el subsidio temporal: crea quiebres en la serie. Si el modelo no lo conoce, falla justo en esas semanas; incluir `subsidio_activo` y mostrar la diferencia es un buen hallazgo para el informe.

### 5.2 Revisar que las tablas quedaron bien 🧱

```sql
%sql
SELECT * FROM workspace.equipo_06_gold.predicciones ORDER BY semana_objetivo DESC;
SELECT * FROM workspace.equipo_06_gold.metricas_modelo ORDER BY fecha_entrenamiento DESC;
```

---

## 6. Semanas 4 y 5

- Semana 5: dejar registrada la predicción de la semana siguiente (puntos extra para la mejor).
- Informe: secciones de extracción (exactitud) y de modelo (frente a la línea base).
- Presentación: explicar "de la foto al dato" y "el modelo" sin jerga.

---

## 7. Problemas comunes

| Problema | Solución |
| --- | --- |
| El OCR lee `3345` sin punto | `normalizar_numero` inserta el punto antes de los 2 últimos dígitos. |
| Asocia el precio al combustible equivocado | Revisa la distancia entre bbox; prueba asociar por fila (misma altura) antes que por columna. |
| EasyOCR no se instala en el cluster | Sáltalo y anótalo como limitación; compara RapidOCR con distintos preprocesamientos. |
| La exactitud del modelo es igual a la de la línea base | Normal con pocas semanas. Documéntalo y explica por qué (precios regulados, cambios poco frecuentes). |
| La validación usa semanas futuras | Ordena por `semana_inicio` y corta por fecha, nunca con `train_test_split` aleatorio. |
