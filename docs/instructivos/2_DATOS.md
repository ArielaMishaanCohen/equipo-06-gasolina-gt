# Guía de rol: Datos (v3)

Proyecto Final ML Engineering · Equipo 06 (confirmar) · Responsable: ________

Esta guía es tu lista de tareas en orden, con los prompts completos. El mapa del proyecto está en `INSTRUCTIVO_GENERAL.md` v3: léete al menos las secciones 0, 1, 2, 3 y 5 (20 minutos). Tu trabajo es casi todo en Databricks y vale la mayor parte de la rúbrica: Bronce (10), reglas de Plata (parte de 15), Oro (10) y Clusters y Job (10).

---

## 1. Tu rol en una tabla

| Qué | Detalle |
| --- | --- |
| Entregas | `bronze.fotos_precios` incremental; fuente complementaria del MEM; reglas de calidad y `silver.precios_rejected`; `gold.precio_semanal`, `gold.variacion_semanal` y `gold.features_modelo` con `COMMENT`; Job `equipo-06-pipeline`; documentación de clusters; (extra) dashboard de Databricks SQL. |
| Dependes de | Catedrático: permisos sobre las external locations. Modelos: `extraer_precios` real (semana 2). Producción: repo reorganizado (esta semana). |
| Dependen de ti | Modelos necesita `gold.features_modelo` para entrenar (semana 3). La API lee tus tablas Oro. |
| Tus archivos | `pipelines/00_setup.sql`, `pipelines/01_bronze.py`, partes de indicadores y features de `pipelines/03_gold.py`, `pipelines/job.json`, `src/gasolina/calidad.py`, `externos.py`, `features.py`, sus tests |
| Tu rama | `datos` |
| No toques | `api/`, `scripts/`, `.github/`, `docker/` (Producción) ni `ocr.py`, `reglas.py`, `extraccion.py`, `modelo.py` (Modelos). Cambios en `pyproject.toml` o `config/config.yaml`: pídeselos a Ariela. |

Hitos:

**Se entrega la próxima semana** (confirmar el día; el plan supone el martes 17). Ya hay permisos de lectura y escritura. "Semana 1 … 5" en esta guía son bloques de días:

| Bloque | Cuándo | Qué tiene que existir |
| --- | --- | --- |
| Semana 1 | Mar 10 (noche) – Mié 11 | `00_setup` corrido; `bronze.fotos_precios` con las fotos del catedrático (incremental); histórico del MEM en Bronce. |
| Semana 2 | Mié 11 – Jue 12 | Reglas de calidad, `silver.precios_rejected` y MERGE idempotente (con la extracción de Modelos). |
| Semana 3 | Vie 13 – Sáb 14 | Tablas Oro con `COMMENT`, Job de 3 tareas con 2 ejecuciones exitosas, clusters documentados. |
| Semana 5 | Dom 15 – Lun 16 | Informe (calidad y clusters), ensayo de la demo (correr el Job con fotos nuevas). |

Contratos que te tocan (sección 5 del general): 5.1 (Bronce), 5.3 (Plata y reglas), 5.4 (Oro y definiciones de semana y dirección). Respétalos al pie de la letra: Modelos y la API los leen tal cual.

---

## 2. Preparación

### 2.1 Tu Mac 💻

```bash
cd "<tu carpeta del proyecto>"
git clone https://github.com/ArielaMishaanCohen/equipo-06-gasolina-gt.git
cd equipo-06-gasolina-gt
git checkout datos
python3.11 -m venv .venv && source .venv/bin/activate
pip install -e ".[api,dev]"
pytest
```

Si sale `No module named 'gasolina'` en una Mac, corre `chflags -R nohidden .venv`.

### 2.2 Git folder en Databricks 🧱

1. Workspace → tu carpeta de usuario → Create → Git folder → URL del repo.
2. Cambia a la rama `datos`.
3. Haz tus commits **desde Databricks** (botón de la rama → Commit & Push): el enunciado pide que los pipelines se sincronicen con Git folders y la rúbrica cuenta los commits de cada integrante.

Primera celda de cada notebook:

```python
%pip install /Workspace/Users/TU_CORREO/equipo-06-gasolina-gt
dbutils.library.restartPython()
```

### 2.3 Rutina de Git

```bash
git checkout main && git pull && git checkout datos && git merge main
# ... trabajas ...
git add -A && git commit -m "datos: <qué hiciste>" && git push
```

Para integrar: Pull Request de `datos` a `main` con el CI en verde.

---

## 3. Semana 1 — Bronce

### 3.1 ⭐ Revisar permisos 🧱 (ahora)

```sql
%sql
LIST 's3://cc3105-cusn-869227452861-us-east-2-an/fotos/';
SHOW GRANTS ON EXTERNAL LOCATION `xloc-cusn`;
SHOW GRANTS ON EXTERNAL LOCATION `xloc-ag`;
SHOW GRANTS ON EXTERNAL LOCATION `xloc-au`;
```

Anota en el chat qué permisos tienen (`READ FILES`, `WRITE FILES`, `CREATE EXTERNAL TABLE`). Mientras no haya escritura, desarrolla los notebooks y pruébalos solo leyendo.

### 3.2 ⭐ Esquemas y tablas (cuando haya permisos de escritura) 🧱

Corre `pipelines/00_setup.sql` (lo deja Ariela en el repo reorganizado). Crea los esquemas `equipo_06_bronze`, `equipo_06_silver` y `equipo_06_gold` (o los nombres que confirme el catedrático). Las tablas son externas con `LOCATION` en el prefijo del equipo, por ejemplo:

```sql
CREATE TABLE IF NOT EXISTS workspace.equipo_06_bronze.fotos_precios (
  path STRING, modificationTime TIMESTAMP, length BIGINT, content BINARY,
  fecha_carpeta DATE, _ingestion_timestamp TIMESTAMP, _source_file STRING)
USING DELTA
LOCATION 's3://cc3105-cusn-869227452861-us-east-2-an/equipo-06/bronze/fotos_precios'
COMMENT 'Fotos de precios tal como llegan, con columnas de auditoría.';
```

### 3.3 ⭐ Histórico del MEM (fuente complementaria) 💻 🧱

Con solo 5 semanas de fotos no se puede entrenar ni validar un modelo. El histórico semanal de precios de referencia del MEM sí lo permite, y usa la misma semana (martes a lunes).

1. Busca el histórico de precios de referencia (MEM, sección de precios de combustibles nacionales; también lo publican AGN, La Hora y Prensa Libre cada martes). Meta: super, regular y diésel por semana, desde enero de 2025 como mínimo, de la Ciudad de Guatemala y modalidad autoservicio.
2. Arma `mem_referencia.csv` con columnas `semana_inicio,combustible,modalidad,region,precio_q_galon,fuente_url`.
3. Anota las fechas del subsidio temporal (inicio 28/04/2026; busca cuándo cambió o terminó) en `eventos_subsidio.csv`.
4. Súbelos tal cual a `s3://cc3105-cusn-…/equipo-06/complementarias/mem/`.
5. Opcional: el CSV del WTI de FRED (`https://fred.stlouisfed.org/graph/fredgraph.csv?id=DCOILWTICO`) a `…/complementarias/fred/`.

Si hay PDFs del MEM, `externos.py` puede parsearlos con pdfplumber; si se complica, completar a mano el CSV es válido y se documenta como "curación manual de fuente externa".

### 3.4 ⭐ Notebook `01_bronze` 🧱

```
PROMPT PARA CLAUDE CODE
Implementa pipelines/01_bronze.py (notebook de Databricks: "# Databricks notebook source" y
"# COMMAND ----------" entre celdas) según la Fase 1 del enunciado
(docs/cc3105_proyecto_final.pdf) y el contrato 5.1 de docs/instructivos/INSTRUCTIVO_GENERAL.md:
1. Widgets: catalogo, esquema_bronze, ruta_fotos (s3://cc3105-cusn-.../fotos/),
   ruta_equipo_bronze (s3://cc3105-cusn-.../equipo-06/), ruta_repo.
2. Leer las fotos con Auto Loader (cloudFiles.format = binaryFile, pathGlobFilter para
   jpg/jpeg/png/heic, trigger availableNow) con checkpoint en
   <ruta_equipo_bronze>/_checkpoints/fotos_precios/, agregando _ingestion_timestamp,
   _source_file y fecha_carpeta (extraída de fotos/AAAA-MM-DD/), y escribir en la tabla
   externa bronze.fotos_precios. Incremental: una segunda corrida no duplica.
3. Cargar las fuentes complementarias de .../complementarias/ (CSV del MEM, subsidio y FRED)
   a tablas Bronce *_raw tal cual, con las mismas columnas de auditoría.
4. Al final: conteo de fotos en la carpeta vs. filas en la tabla (deben coincidir) y una
   verificación de que no hay paths duplicados.
Si Auto Loader no está disponible en el cómputo, usa spark.read.format("binaryFile") + MERGE
por path como alternativa, controlada por un widget "modo".
```

Criterio de aceptación: filas en `bronze.fotos_precios` = fotos en la carpeta; correrlo dos veces no duplica. Toma captura de ambas corridas.

---

## 4. Semana 2 — Reglas de calidad y Plata

### 4.1 ⭐ Reglas de calidad 💻

```
PROMPT PARA CLAUDE CODE
Implementa src/gasolina/calidad.py con las reglas del contrato 5.3 de
docs/instructivos/INSTRUCTIVO_GENERAL.md: rango_precio (rango desde config.yaml),
combustible_valido, fecha_no_futura, consistencia_gasolinas y confianza_minima. Una función
aplicar_reglas(df_pandas) -> (df_validos, df_rechazados) donde df_rechazados lleva motivo y
regla. Que también exista una versión para Spark (expresiones de columnas) para usarla en
02_silver sin pasar por pandas. Tests unitarios con casos sintéticos en tests/test_calidad.py.
No toques api/, scripts/ ni los archivos de Modelos.
```

### 4.2 ⭐ Cuarentena y MERGE en `02_silver` 🧱 (junto con Modelos)

Modelos escribe la parte de extracción del notebook; tú agregas, al final:

- Aplicar `calidad.py`; los válidos van a `silver.precios` con `MERGE` por `fecha + ubicacion + combustible + modalidad` (con `no_indica` en vez de `null`); los rechazados a `silver.precios_rejected`.
- El histórico del MEM pasa a `silver.mem_referencia` (limpio, tipado, misma semana).
- Resumen al final: fotos procesadas, filas válidas, filas rechazadas por regla.

Criterio de aceptación: una segunda corrida deja exactamente los mismos conteos.

---

## 5. Semana 3 — Oro, Job y clusters

### 5.1 ⭐ Indicadores y features en `03_gold` 🧱

```
PROMPT PARA CLAUDE CODE
Implementa la primera parte de pipelines/03_gold.py (Fase 3 del enunciado, contrato 5.4 del
instructivo general): con widgets catalogo, esquemas, ruta_equipo_oro y umbral_q (0.10):
1. gold.precio_semanal: semana de martes a lunes (fórmula de la sección 5.4), promedio, min,
   max y n_registros por semana y combustible. Fuente "fotos" (silver.precios) y "mem"
   (silver.mem_referencia) como filas separadas.
2. gold.variacion_semanal: dif_q y dif_pct contra la semana anterior y direccion con el
   umbral (sube/baja/se_mantiene).
3. gold.features_modelo: var_q_1 a var_q_4, prom_movil_4, dif_super_diesel, direccion_actual,
   wti_var_1 y subsidio_activo si existen, y el objetivo direccion_siguiente (null en la última
   semana). Implementa la lógica en src/gasolina/features.py (pandas) con tests.
4. Tablas externas en <ruta_equipo_oro>/gold/<tabla>/, escritas con overwrite (idempotentes),
   y COMMENT ON TABLE y ALTER TABLE ... ALTER COLUMN ... COMMENT explicando cada métrica.
Debe correr aunque silver.precios esté vacía (usa solo el MEM). La parte de modelo y
predicciones la agrega Modelos al final del mismo notebook.
```

### 5.2 ⭐ Job `equipo-06-pipeline` 🧱

1. Jobs & Pipelines → Create → Job → nombre `equipo-06-pipeline`.
2. Tres tareas tipo Notebook, fuente Git (repo, rama `main`):
   1. `bronze` → `pipelines/01_bronze`
   2. `silver` → `pipelines/02_silver` (depende de `bronze`)
   3. `gold` → `pipelines/03_gold` (depende de `silver`)
3. Parámetros del Job (no escritos en el código): catálogo, esquemas, rutas, `umbral_q`.
4. Cómputo: job cluster (o el que indique el catedrático; en Free Edition, serverless de jobs). **No** el cluster interactivo.
5. Trigger: **File arrival** sobre `s3://cc3105-cusn-…/fotos/` o programación semanal los martes 7:00 (America/Guatemala).
6. Notifications: correo **On failure** a los 3 integrantes.
7. Comparte el Job con el catedrático (Permissions → Can view / Can manage run).
8. Corre "Run now" con fotos de dos semanas distintas y toma captura del historial de ejecuciones y de la duración de cada tarea.

### 5.3 Dos ejecuciones exitosas

Necesitas evidencia de 2 corridas con fotos de semanas distintas. Si el catedrático todavía no sube la segunda semana, coordina con él cuándo, o documenta la corrida con las fotos propias del equipo como segunda semana.

### 5.4 ⭐ Documentar el cluster interactivo

Anota para el informe: versión de Databricks Runtime, tipo de nodo, número de workers, autoterminación (**máximo 30 minutos**) y librerías instaladas (paquete `gasolina`, RapidOCR, MLflow). Explica la diferencia de costo y propósito entre el cluster interactivo (desarrollo, se paga mientras está encendido) y el job cluster (se crea para la corrida y se apaga solo).

### 5.5 Extra: dashboard de Databricks SQL

Dashboards → Create → fuentes `gold.precio_semanal`, `gold.variacion_semanal` y `gold.predicciones`: línea del precio semanal por combustible, tabla de direcciones y la predicción vigente. Cuenta para los puntos extra.

---

## 6. Semanas 4 y 5

- Demo: correr el Job con fotos nuevas delante del jurado (ten listo cuáles).
- Informe: secciones de calidad de datos (reglas, % de rechazo) y de clusters.
- Revisa que tus commits estén en `main`.

---

## 7. Problemas comunes

| Problema | Solución |
| --- | --- |
| `PERMISSION_DENIED` en `LIST` o `CREATE TABLE … LOCATION` | Faltan permisos sobre la external location: avísale a Ariela para pedirlos. |
| Auto Loader no encuentra fotos nuevas | Revisa el `pathGlobFilter` y que el checkpoint esté en el prefijo del equipo. |
| El MERGE duplica | `modalidad` o `ubicacion` en `null`: rellenar con `no_indica`. |
| La semana sale corrida | Spark: `dayofweek` 1 = domingo; el martes es 3. Usa la fórmula del contrato 5.4. |
| El cluster interactivo sigue encendido | Autoterminación ≤ 30 min; apágalo al terminar. |
