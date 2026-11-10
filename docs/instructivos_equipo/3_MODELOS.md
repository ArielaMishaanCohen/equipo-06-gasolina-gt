# Instructivo de rol: Modelos

Proyecto Final ML Engineering · Grupo 6 · Responsable: ________

Este documento es tu lista de tareas en orden, con los prompts completos. El mapa del proyecto (arquitectura, contratos, calendario) está en `INSTRUCTIVO_GENERAL.md`; léete al menos las secciones 1, 2 y 4 (15 minutos). Todo tu trabajo es con el servidor apagado: en tu Mac y en Databricks.

---

## 1. Tu rol en una tabla

| Qué | Detalle |
| --- | --- |
| Entregas | Etiquetas manuales; lectura de metadata EXIF; OCR + reglas + fusión de las dos rutas; evaluación; experimentos de OCR en MLflow; modelo de pronóstico; modelos registrados en Unity Catalog; artifacts `ocr_config.json`, `forecast.joblib`, `forecast_meta.json` y `predicciones.json`. |
| Dependes de | Producción: repo base (hoy). Datos: `g6_oro.features_forecast` (miércoles 10:00 p. m.) para el pronóstico y las fotos en bronce para los experimentos. |
| Dependen de ti | La API de Ariela y el notebook `02_plata` de Datos llaman a tu `extraer_precios`. Por eso su salida tiene que respetar el contrato 4.1 exactamente. |
| Tus archivos | `metadata.py`, `ocr.py`, `reglas.py`, `extraccion.py`, `forecast.py`, las funciones `extraer` y `evaluar` de `cli.py`, sus tests, `notebooks/04_experimentos_ocr.py`, `notebooks/05_forecast.py` |
| Tu rama | `modelos` |
| No toques | `api/`, `sync.py`, `docker/`, `scripts/`, `.github/` (Producción) ni `externos.py`, `features.py` y los notebooks 00–03 y 06 (Datos). Si necesitas una dependencia nueva en `pyproject.toml` o un valor en `config/config.yaml`, pídeselo a Ariela. |

Fechas límite:

| Hito | Cuándo | Qué tiene que existir |
| --- | --- | --- |
| Hoy | Martes 10 | `etiquetas.csv` completo (y fotos nuevas si pueden). |
| H1 | Miércoles 11, 10:00 p. m. | Metadata + OCR + reglas + fusión funcionando en tu Mac, con `gasolina-evaluar`, mergeado a `main` (avisa en el chat: "OCR real en main"). |
| H2 | Jueves 12, 2:00 p. m. | Experimentos de OCR y de pronóstico en MLflow, modelos registrados y los 4 artifacts en `g6_oro/artifacts`. |
| H3 | Jueves 12, 10:00 p. m. | Simulacro en llamada. |
| Viernes | En clase | Generar tráfico real contra el servidor y ayudar con el video. |

Contrato clave (sección 4.1 del general): `extraer_precios` devuelve siempre todas las claves, con `null` donde no se pudo leer, y `"modo": "real"`. Si necesitas cambiar algo del contrato, avísalo en el chat antes de tocar código.

---

## 2. Hoy, sin necesitar el repo ⏸

### 2.1 ⭐ Etiquetas manuales (la "verdad" para medir el OCR)

Sin esto no se puede decir qué tan bueno es el modelo. Abre cada foto (te las pasa Ariela) en Vista Previa, haz zoom en las 4 pantallitas y en la pantalla de arriba, y llena este archivo. Guárdalo como `datos/etiquetas.csv`:

```csv
archivo,diesel,regular,super,vpower,venta_total,galones
IMG_8271.jpg,35.59,37.09,38.09,38.59,150.00,3.938
IMG_8286.jpg,,,,,,
IMG_8304.jpg,,,,,,
IMG_8322.jpg,,41.09,42.09,42.59,150.00,
IMG_8325.jpg,,,,,,
```

Ya está lo que se alcanza a leer en dos fotos. Verifícalo con zoom y completa lo que falta. Si un número no se lee bien ni a simple vista, déjalo vacío y anótalo como limitación para el reporte. Revisa también si se cumplen las reglas Super = Regular + 1.00 y V-Power = Super + 0.50 en las 5 fotos.

Cuando esté listo, mándaselo a la persona de Datos (o súbelo tú) a `/Volumes/workspace/g6_bronce/crudos/etiquetas/etiquetas.csv`.

✨ Recomendado: tomen más fotos esta semana (3 a 5 cada uno, en distintas gasolineras Shell, con la ubicación del iPhone activada, que se vean "Esta Venta" y las 4 pantallitas). Con 20 a 30 fotos la evaluación del OCR es mucho más creíble. Agrégalas a `etiquetas.csv` y súbelas a `crudos/fotos/`.

### 2.2 Acceso a Databricks 🧱

Entra con tu invitación del profesor (búscala en tu correo, también en spam). Si no la tienes, escríbele hoy.

---

## 3. Cuando el repo exista (Ariela avisa en el chat)

### 3.1 Tu Mac 💻

Estructura de carpetas (para que funcionen las rutas `../datos` de los prompts):

```
<tu carpeta del proyecto>/
  datos/            # las fotos originales + etiquetas.csv
  gasolina-mlops/   # el repo
```

```bash
cd "<tu carpeta del proyecto>"
git clone https://github.com/USUARIO_DE_ARIELA/gasolina-mlops.git
cd gasolina-mlops
git checkout modelos
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Abre Claude Code en la carpeta `gasolina-mlops` para los prompts de abajo.

### 3.2 Git folder en Databricks 🧱

1. Workspace → tu carpeta de usuario → Create → Git folder.
2. URL: `https://github.com/USUARIO_DE_ARIELA/gasolina-mlops.git` (si te pide conectar GitHub: Settings → Linked accounts → GitHub).
3. Cambia a la rama `modelos`.
4. Después de cada push desde tu Mac: botón de la rama → Pull.

Primera celda de cada notebook:

```python
%pip install -e /Workspace/Users/TU_CORREO/gasolina-mlops
dbutils.library.restartPython()
```

(Si `-e` falla en serverless, quítalo.)

### 3.3 Rutina de Git

```bash
git checkout main && git pull
git checkout modelos && git merge main
# ... trabajas ...
git add -A && git commit -m "Modelos: <qué hiciste>" && git push
```

Para integrar: Pull Request de `modelos` a `main`, CI en verde y merge. Avisa en el chat.

---

## 4. Tareas en orden

### 4.1 ⭐ Metadata (martes en la noche) 💻

```
PROMPT PARA CLAUDE CODE
Implementa src/gasolina/metadata.py. Función leer_metadata(ruta) -> dict con:
archivo, fecha_hora (ISO, de DateTimeOriginal o DateTime), lat, lon (decimales con signo,
convertidos desde los grados/minutos/segundos del EXIF GPS), altitud, modelo_camara,
ancho, alto, y sha256 del archivo (para trazabilidad/deduplicación). Las claves deben ser
exactamente las del contrato 4.1 de docs/INSTRUCTIVO_GENERAL.md.
Debe soportar JPG y HEIC (registra pillow_heif). Si falta algún campo, pon None, no truene.
Luego crea tests/test_metadata.py que la pruebe con ../datos/IMG_8271.jpg si existe
(skip si no existe). Corre los tests y muéstrame la salida para las 5 fotos de ../datos/.
```

Resultado esperado: fechas del 9 al 30 de julio de 2026 y lat ≈ 14.5600, lon ≈ −90.4628 en todas.

### 4.2 ⭐ OCR + reglas + fusión (miércoles) 💻

```
PROMPT PARA CLAUDE CODE
Implementa ocr.py, reglas.py y extraccion.py para leer los 4 precios de bombas Shell.
El diccionario que devuelve extraer_precios debe respetar EXACTAMENTE el contrato 4.1 de
docs/INSTRUCTIVO_GENERAL.md: la API y el notebook de plata dependen de esas claves.
No toques api/, sync.py, docker/ ni scripts/ (son de otra persona).

Contexto de las fotos (bombas Gilbarco, ver ../datos/*.jpg):
- Arriba hay una pantalla grande "Esta Venta" con el total en quetzales (ej. 150.00) y
  debajo los galones con 3 decimales (ej. 3.938).
- Abajo hay 4 pantallitas LCD de "Precio por galón", de izquierda a derecha:
  Diesel, Regular (FuelSave), Super (FuelSave), V-Power. Formato NN.NN (ej. 37.09).
- Los dígitos son LCD de 7 segmentos; el OCR puede confundir 0/8, 1/7, 5/6 o perder el punto.

ocr.py:
- Clase base OcrEngine con método leer(imagen_np) -> lista de detecciones
  {texto, confianza, bbox(x1,y1,x2,y2)}.
- RapidOcrEngine usando rapidocr_onnxruntime (RapidOCR()).
- EasyOcrEngine (import perezoso, allowlist "0123456789.") solo si está instalado.
- Preprocesamientos configurables: "ninguno", "gris_clahe", "gris_clahe_x2" (upscale 2x),
  "binarizado". Reduce la imagen a ~1600 px de alto antes de OCR para que sea rápido.

reglas.py:
- normalizar_numero(texto): quitar espacios, cambiar , por ., si hay 4 dígitos sin punto
  insertar punto antes de los 2 últimos; devolver float o None.
- Candidatos a precio: valores con 2 decimales en el rango [precio_min, precio_max] del config
  (por defecto 20–60 Q/gal). Excluir el total de venta (ej. 150.00, rango > 60) y los galones
  (3 decimales).
- Asignación: de los candidatos, tomar el grupo de 4 que estén aproximadamente en la misma
  fila (centro y similar, tolerancia relativa a la altura de la imagen) y ordenarlos por x:
  diesel, regular, super, vpower. Si hay menos de 4, asignar los que se pueda por posición
  relativa y dejar None el resto.
- Validaciones (cada una devuelve {nombre, estado: ok|falla|advertencia, mensaje}):
  1. formato_y_rango
  2. orden_gasolinas: regular < super < vpower
  3. diferencias_tipicas: super - regular ≈ 1.00 y vpower - super ≈ 0.50 (tolerancia 0.05);
     es "advertencia", no error
  4. venta_entre_galones: si se leyó total y galones, total/galones debe ser ≈ alguno de
     los 4 precios (tolerancia 0.02)
  5. referencia_mem (opcional, si se pasa un dict de referencia): |precio - ref| <= 15%
- Correcciones: si una validación de diferencias falla y se puede reconstruir un precio
  faltante o claramente mal leído desde los otros (ej. super = regular + 1.00), proponerlo
  marcándolo como "inferido" (nunca sobrescribir sin marcar).
- score_confianza 0-1: combina confianza promedio del OCR y fracción de validaciones ok.

DOS RUTAS + FUSIÓN (muy importante, lo pidió el profesor):
- Ruta A (arriba): detectar el total de "Esta Venta" (valor con 2 decimales, típicamente
  > 60, en la mitad superior de la imagen) y los galones (valor con 3 decimales justo debajo).
  precio_A = round(total / galones, 2).
- Ruta B (abajo): los 4 precios de las pantallitas como se describe arriba.
- fusionar(ruta_a, ruta_b, reglas): sigue estos pasos:
  1. buscar qué precio de B está a <= 0.02 de precio_A → combustible_despachado, ambos
     verificados (fuente "ambas");
  2. si ninguno coincide pero precio_A coincide con un precio implicado por las reglas,
     corregir ese precio de B (fuente "corregido_por_ruta_A");
  3. si B falló, reconstruir con reglas desde precio_A (fuente "inferido");
  4. registrar las discrepancias.
- Parámetro estrategia ∈ {"solo_A", "solo_B", "fusion"} en extraer_precios y en el CLI.

extraccion.py:
- extraer_precios(ruta, motor="rapidocr", preproc="gris_clahe", estrategia="fusion",
  referencia=None) -> dict del contrato 4.1: metadata, ruta_a {total, galones, precio_a},
  precios {diesel, regular, super, vpower}, fuentes por precio
  ("ruta_A"|"ruta_B"|"ambas"|"corregido_por_ruta_A"|"inferido"), combustible_despachado,
  validaciones, score_confianza, detecciones_crudas, tiempo_ms, version_modelo, "modo": "real".

cli.py (solo las funciones extraer y evaluar):
- gasolina-extraer RUTA [--motor] [--preproc] [--estrategia] → imprime JSON bonito.
- gasolina-evaluar --etiquetas ../datos/etiquetas.csv --imagenes ../datos [--motor] [--preproc]
  → por foto y global: accuracy exacta por precio (|pred-real| < 0.005), MAE, % de fotos con
  los 4 correctos, tiempo promedio. Ignora celdas vacías del CSV.

Escribe tests unitarios para reglas.py con casos sintéticos (no necesitan imágenes).
gasolina-evaluar también debe medir la ruta A por separado (precio_A vs total/galones de
etiquetas.csv) y reportar métricas por estrategia (solo_A, solo_B, fusion).
Corre gasolina-evaluar con las combinaciones de motor rapidocr, los 4 preprocesamientos y
las 3 estrategias y muéstrame una tabla de resultados. Si la accuracy es baja, analiza las
detecciones crudas de las fotos que fallan y propone mejoras (ej. recortar la franja inferior
donde están las pantallitas antes del OCR). Implementa la mejora y vuelve a evaluar.
```

Cómo sabes que quedó bien:

```bash
gasolina-extraer ../datos/IMG_8271.jpg
```

Debe devolver `regular: 37.09, super: 38.09, vpower: 38.59` (y diesel si se lee), con validaciones en `ok`.

Si el OCR lee mal los dígitos de 7 segmentos, la mejora más efectiva suele ser:

1. Recortar solo la franja de las 4 pantallitas (detectarla con el OCR en una primera pasada, o con las pantallitas oscuras).
2. Ampliar ese recorte 3x.
3. Volver a leer.

```
PROMPT PARA CLAUDE CODE
Implementa una segunda pasada de OCR sobre la franja de las pantallitas ampliada 3x
(parámetro segunda_pasada=True/False en extraer_precios y en el CLI) y compara con
gasolina-evaluar contra la versión sin segunda pasada.
```

Antes del merge, verifica que la API de Ariela siga funcionando con tu código:

```bash
pip install -e ".[api,dev]"
pytest
gasolina-api &
sleep 5 && curl -F "foto=@../datos/IMG_8271.jpg" http://localhost:8000/extraer
kill %1
```

Checklist H1:

- [ ] `gasolina-evaluar` da una tabla con métricas por motor, preprocesamiento y estrategia (guárdala: va al reporte).
- [ ] Hay al menos una configuración con ≥ 90 % de precios correctos en las fotos etiquetadas (meta). Si no se llega, documenta por qué y cómo las reglas lo compensan.
- [ ] `pytest` pasa (incluidos los tests de la API).
- [ ] PR a `main` con CI en verde y merge; aviso "OCR real en main".

### 4.3 ⭐ Experimentos de OCR en MLflow (jueves en la mañana) 🧱

Esta es la parte de "MLOps de verdad": no elegimos el motor por gusto, sino con experimentos registrados.

```
PROMPT PARA CLAUDE CODE
Crea notebooks/04_experimentos_ocr.py (notebook de Databricks) que:
1. Lea etiquetas.csv desde /Volumes/<cat>/g6_bronce/crudos/etiquetas/etiquetas.csv
   (yo la subiré ahí) y las fotos desde /Volumes/<cat>/g6_bronce/crudos/fotos/.
2. Use mlflow.set_experiment("/Users/<correo>/g6_ocr_gasolina").
3. Para cada combinación motor ∈ {rapidocr, easyocr (si se puede instalar)} × preproc ∈
   {ninguno, gris_clahe, gris_clahe_x2, binarizado} × segunda_pasada ∈ {False, True} ×
   estrategia ∈ {solo_A, solo_B, fusion}:
   una corrida de MLflow con params, métricas (accuracy_precio, mae, pct_fotos_4_correctos,
   tiempo_ms_promedio, pct_validaciones_ok) y como artifact un CSV con las predicciones
   por foto.
4. Al final, una tabla comparativa ordenada por accuracy y tiempo, y escribir el ganador
   (motor, preproc, segunda_pasada, estrategia) en /Volumes/<cat>/g6_oro/artifacts/ocr_config.json
   con el contrato 4.2 de docs/INSTRUCTIVO_GENERAL.md.
5. Registrar el pipeline de extracción como modelo pyfunc de MLflow en Unity Catalog
   (<cat>.g6_oro.extractor_gasolina): un PythonModel cuyo predict reciba un DataFrame con
   columna imagen_base64 y devuelva los precios. Incluir pip_requirements.
Si EasyOCR no se puede instalar o descargar sus pesos (restricción de internet), saltarlo
y anotarlo en el notebook como limitación.
```

Revisa que `etiquetas.csv` esté en `crudos/etiquetas/`.

Para ver los resultados: barra izquierda → Experiments → `g6_ocr_gasolina`. Selecciona varias corridas → Compare. Toma capturas.

### 4.4 ⭐ Pronóstico (jueves, en cuanto Datos avise que `features_forecast` está lista) 🧱

Qué se pronostica: el precio de referencia MEM (Ciudad de Guatemala) de la próxima semana, por combustible. Con el spread estación-vs-MEM de `comparacion_mem`, también se puede estimar el precio en "nuestra" estación.

```
PROMPT PARA CLAUDE CODE
Crea notebooks/05_forecast.py (notebook de Databricks) usando <cat>.g6_oro.features_forecast:
1. Validación temporal (TimeSeriesSplit o walk-forward con las últimas 8-10 semanas como test),
   NUNCA mezclar futuro en entrenamiento.
2. Modelos, cada uno con su corrida MLflow (experimento /Users/<correo>/g6_forecast_gasolina):
   a) baseline ingenuo: precio de la próxima semana = precio de esta semana
   b) Ridge con lags + exógenas + subsidio
   c) GradientBoostingRegressor con los mismos features
   Un modelo por combustible o uno global con one-hot del combustible (prueba ambos si da
   tiempo). Métricas: MAE y RMSE en Q, MAPE, y "mejora vs baseline" (%).
3. Gráfica real vs predicho en test (artifact png) e importancia de variables / coeficientes.
4. Registrar el mejor en Unity Catalog como <cat>.g6_oro.forecast_gasolina con alias
   "champion" (mlflow.set_registry_uri("databricks-uc")). Solo promover si mejora al baseline;
   si no mejora, promover el baseline y documentarlo (eso también es un resultado válido).
5. Generar predicciones para la próxima semana y guardarlas en <cat>.g6_oro.predicciones
   (fecha_generacion, semana_objetivo, combustible, prediccion, modelo, version).
6. Exportar a /Volumes/<cat>/g6_oro/artifacts/: forecast.joblib (modelo champion),
   forecast_meta.json y predicciones.json, ambos con el contrato 4.2 de
   docs/INSTRUCTIVO_GENERAL.md. La API de producción solo lee predicciones.json.
Explica en markdown, dentro del notebook, cómo interpretar cada resultado.
```

Cuidado (y punto fuerte para el reporte): el subsidio crea quiebres en la serie. Si el modelo no sabe del subsidio, va a fallar justo en esas semanas. Incluir la dummy y mostrar la diferencia es un excelente hallazgo.

Si `features_forecast` se atrasa, empieza el notebook con el CSV consolidado del MEM (`crudos/mem/precios_mem_consolidado.csv`) y solo con lags, y agrega las exógenas cuando llegue la tabla.

Checklist H2:

- [ ] Experimentos de OCR y de forecast visibles en MLflow con varias corridas.
- [ ] Modelos registrados en Unity Catalog (Catalog → `g6_oro` → Models), el de pronóstico con alias `champion`.
- [ ] `ocr_config.json`, `forecast.joblib`, `forecast_meta.json` y `predicciones.json` en `g6_oro/artifacts/`, todos con `"origen": "databricks"`.
- [ ] Notebooks 04 y 05 en `main` (Datos agrega `05_forecast` al job semanal).
- [ ] Aviso en el chat: "Artifacts de modelos en oro".

---

## 5. Viernes en la clase ▶ (tu papel)

| Minuto | Qué hacer |
| --- | --- |
| 15–25 | Cuando Ariela diga que el despliegue está listo, desde la carpeta del repo: `python scripts/generar_trafico.py --url http://159.65.111.14:8000 --carpeta ../datos --repeticiones 3`. Luego sube 2 o 3 fotos nuevas desde la página. Captura de la tabla de resultados. |
| 30–45 | Video de la demo (tú explicas la pestaña "Leer foto": ruta A, ruta B, fusión y validaciones). |

---

## 6. Para el reporte (después del viernes)

Tú escribes las secciones 5 (Modelo de extracción) y 6 (Modelo de pronóstico) del reporte (estructura en la sección 10.2 del general). Junta: la tabla de `gasolina-evaluar`, las capturas de MLflow Compare (OCR y forecast), la tabla solo_A vs solo_B vs fusión, la gráfica real vs predicho, la comparación contra el baseline, el efecto del subsidio y 2 o 3 ejemplos de aciertos y errores con imagen.

---

## 7. Problemas comunes

| Problema | Causa probable | Solución |
| --- | --- | --- |
| El OCR lee `3809` sin punto | Típico en LCD | `normalizar_numero` inserta el punto. Revisa los tests. |
| `rapidocr_onnxruntime` no instala | Versión de Python | Usa Python 3.10 o 3.11 en el venv. |
| EasyOCR no instala en Databricks | Internet restringido o pesos grandes | Saltarlo y documentarlo como limitación (lo pide el prompt). |
| `%pip install` falla en Databricks | Ruta del repo mal escrita | Clic derecho en la carpeta → Copy path. |
| La API de Ariela truena con tu código | Clave del contrato distinta | Compara tu salida con el contrato 4.1 clave por clave. |
| El modelo de pronóstico no le gana al baseline | Pocas semanas o quiebres por subsidio | Es un resultado válido: promueve el baseline y documéntalo. |

Para cualquier error, pégaselo a Claude Code:

```
PROMPT PARA CLAUDE CODE
Estoy en el paso [X.Y] del instructivo [general / de mi rol]. Corrí: [comando]. Me salió:
[error completo]. Estoy en [mi Mac / el servidor / Databricks]. Explícame qué significa y
dame el arreglo paso a paso.
```
