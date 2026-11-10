# Instructivo de rol: Datos

Proyecto Final ML Engineering · Grupo 6 · Responsable: ________

Este documento es tu lista de tareas en orden, con los prompts completos. El mapa del proyecto (arquitectura, contratos, calendario) está en `INSTRUCTIVO_GENERAL.md`; léete al menos las secciones 1, 2 y 4 (15 minutos). Todo tu trabajo es con el servidor apagado: Databricks está disponible siempre.

---

## 1. Tu rol en una tabla

| Qué | Detalle |
| --- | --- |
| Entregas | Capas bronce, plata y oro en Databricks; ingesta de fotos, MEM y FRED; `features_forecast`; artifacts `reglas.json`, `historico.json` y `monitoreo.json`; jobs programados; monitoreo con alertas; dashboard. |
| Dependes de | Producción: repo base (hoy) y logs simulados (jueves 2:00 p. m.). Modelos: OCR real en `main` (miércoles noche) para procesar las fotos en plata. Mientras tanto, el OCR está en modo stub y tus notebooks deben correr igual. |
| Dependen de ti | Modelos necesita `g6_oro.features_forecast` el miércoles en la noche para entrenar el pronóstico. La API necesita tus 3 artifacts. |
| Tus archivos | `src/gasolina/externos.py`, `src/gasolina/features.py`, sus tests, `notebooks/00_setup.sql`, `01_bronce_ingesta.py`, `02_plata.py`, `03_oro.py`, `06_monitoreo.py`, `notebooks/README.md` |
| Tu rama | `datos` |
| No toques | `api/`, `sync.py`, `docker/`, `scripts/`, `.github/` (Producción) ni `ocr.py`, `reglas.py`, `extraccion.py`, `forecast.py` (Modelos). Si necesitas un cambio en `pyproject.toml` o `config/config.yaml`, pídeselo a Ariela. |

Fechas límite:

| Hito | Cuándo | Qué tiene que existir |
| --- | --- | --- |
| Hoy | Martes 10 | PDF del MEM, CSV de FRED y fechas del subsidio descargados; esquemas y volúmenes creados; fotos en bronce. |
| H1 | Miércoles 11, 10:00 p. m. | Bronce y plata de MEM y FRED; `g6_oro.features_forecast` lista (avísale a Modelos). |
| H2 | Jueves 12, 2:00 p. m. | Plata y oro con las fotos procesadas con el OCR real; `reglas.json` e `historico.json`; job `g6_pipeline_semanal` en verde. |
| H3 | Jueves 12, 10:00 p. m. | `06_monitoreo` y el job `g6_monitoreo_diario` funcionando con los logs simulados; dashboard publicado; simulacro en llamada. |
| Viernes | En clase | Correr el monitoreo con los logs reales del servidor y tomar capturas. |

Contratos que te tocan (sección 4 del general): 4.1 (lo que devuelve `extraer_precios`, que usas en `02_plata`), 4.2 (`reglas.json`, `historico.json`, `monitoreo.json`), 4.3 (logs que lees en `06_monitoreo`) y 4.4 (nombres de tablas). Respétalos al pie de la letra: la API de Ariela los lee tal cual.

---

## 2. Hoy, sin necesitar el repo ⏸

### 2.1 Acceso a Databricks 🧱

Entra con tu invitación del profesor (búscala en tu correo, también en spam). Si no la tienes, escríbele hoy. Anota la URL del workspace.

### 2.2 ⭐ Esquemas y volúmenes 🧱

En un notebook `00_setup` (si Ariela ya lo hizo, solo verifica en Catalog que existan):

```sql
%sql
CREATE SCHEMA IF NOT EXISTS workspace.g6_bronce;
CREATE SCHEMA IF NOT EXISTS workspace.g6_plata;
CREATE SCHEMA IF NOT EXISTS workspace.g6_oro;

CREATE VOLUME IF NOT EXISTS workspace.g6_bronce.crudos;
CREATE VOLUME IF NOT EXISTS workspace.g6_oro.artifacts;
```

Si sale `PERMISSION_DENIED`, avisa en el chat (hay que preguntarle al profesor qué catálogo usar). Si el profesor les dio una external location de S3, usen en su lugar:

```sql
%sql
CREATE EXTERNAL VOLUME IF NOT EXISTS workspace.g6_bronce.crudos
  LOCATION 's3://NOMBRE-BUCKET/g6/bronce/';
CREATE EXTERNAL VOLUME IF NOT EXISTS workspace.g6_oro.artifacts
  LOCATION 's3://NOMBRE-BUCKET/g6/oro/artifacts/';
```

### 2.3 ⭐ Fotos a bronce 🧱

1. Catalog → `workspace` → `g6_bronce` → Volumes → `crudos`.
2. Create directory → `fotos`. Entra → Upload to this volume → las 5 fotos `.jpg` que te pasó Ariela (originales, sin editar: bronce es una copia fiel).
3. Crea también los directorios `mem`, `fred`, `etiquetas` y `api_logs` (si no existen).

Ruta final de una foto: `/Volumes/workspace/g6_bronce/crudos/fotos/IMG_8271.jpg`.

### 2.4 ⭐ PDF del MEM 💻

El MEM no tiene una API. Publica informes PDF ("Informe ejecutivo de precios de los combustibles"), y cada uno trae una tabla de precios promedio de las últimas ~7 semanas para Super, Regular y Diésel (y precios de referencia vs monitoreados). Ejemplo:
`https://mem.gob.gt/wp-content/uploads/2026/05/INFORME-EJECUTIVO-DE-PRECIOS-DE-LOS-COMBUSTIBLES-2026-05-27.pdf`

1. Entra a mem.gob.gt → Hidrocarburos → Precios (o busca en Google "INFORME EJECUTIVO DE PRECIOS DE LOS COMBUSTIBLES site:mem.gob.gt").
2. Descarga un informe cada ~6 semanas, de enero 2025 a hoy (unos 12–15 PDF). Juntos cubren todo el periodo.
3. Guárdalos en `datos/mem/` (al lado del repo, ver 3.1) sin renombrarlos.
4. Súbelos a `/Volumes/workspace/g6_bronce/crudos/mem/`.

### 2.5 ⭐ Fechas del subsidio 💻

El "Apoyo Social Temporal" empezó el 28/04/2026 (Q5 gasolinas, Q8 diésel). Busca en noticias cuándo terminó o cambió (los precios de julio en las fotos sugieren un cambio a mediados de julio). Guarda `datos/mem/eventos_subsidio.csv` y súbelo también a `crudos/mem/`:

```csv
fecha_inicio,fecha_fin,producto,monto_q
2026-04-28,AAAA-MM-DD,gasolinas,5.00
2026-04-28,AAAA-MM-DD,diesel,8.00
```

Anota los links de las noticias: van al reporte.

### 2.6 ⭐ CSV de FRED 💻

Descárgalos con el navegador (por si la red de Databricks los bloquea) y súbelos a `crudos/fred/`:

| Serie | Qué es | URL |
| --- | --- | --- |
| `DGASUSGULF` | Gasolina regular convencional, Costa del Golfo EE. UU. (USD/galón, diario) | `https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGASUSGULF` |
| `DDFUELUSGULF` | Diésel ULSD, Costa del Golfo (USD/galón, diario) | `https://fred.stlouisfed.org/graph/fredgraph.csv?id=DDFUELUSGULF` |
| `DCOILWTICO` | Petróleo WTI (USD/barril, diario) | `https://fred.stlouisfed.org/graph/fredgraph.csv?id=DCOILWTICO` |

---

## 3. Cuando el repo exista (Ariela avisa en el chat)

### 3.1 Tu Mac 💻

Estructura de carpetas (para que funcionen las rutas `../datos` de los prompts):

```
<tu carpeta del proyecto>/
  datos/            # fotos, mem/ (PDF + subsidio), fred/
  gasolina-mlops/   # el repo
```

```bash
cd "<tu carpeta del proyecto>"
git clone https://github.com/USUARIO_DE_ARIELA/gasolina-mlops.git
cd gasolina-mlops
git checkout datos
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Abre Claude Code en la carpeta `gasolina-mlops` para los prompts de abajo.

### 3.2 Git folder en Databricks 🧱

1. Workspace → tu carpeta de usuario → Create → Git folder.
2. URL: `https://github.com/USUARIO_DE_ARIELA/gasolina-mlops.git` (si te pide conectar GitHub: Settings → Linked accounts → GitHub).
3. Cambia a la rama `datos` con el botón de la rama.
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
git checkout datos && git merge main
# ... trabajas ...
git add -A && git commit -m "Datos: <qué hiciste>" && git push
```

Para integrar: Pull Request de `datos` a `main` en GitHub, esperar el CI en verde y hacer merge. Avisa en el chat.

---

## 4. Tareas en orden

### 4.1 ⭐ Parser del MEM (miércoles en la mañana) 💻

```
PROMPT PARA CLAUDE CODE
En src/gasolina/externos.py implementa parsear_informe_mem(ruta_pdf) usando pdfplumber.
Los PDFs están en ../datos/mem/. Cada informe del MEM tiene una tabla de "precios promedio"
semanales (fechas tipo 23/04, 27/04... y filas Gasolina Superior, Gasolina Regular,
Combustible Diésel) y una tabla de precio de referencia vs monitoreado (AutoServicio y
Servicio Completo). Inspecciona primero 2-3 PDFs (imprime el texto y las tablas que detecta
pdfplumber) para entender el formato real antes de escribir el parser.
Devuelve un DataFrame largo: fecha (date, infiriendo el año desde la fecha del informe en el
nombre del archivo), combustible (super|regular|diesel), precio_promedio, fuente_pdf.
Si alguna tabla no se puede parsear, registra un warning y sigue. Luego junta todos los
PDFs, elimina duplicados (misma fecha y combustible: quedarse con el informe más reciente),
y guarda ../datos/mem/precios_mem_consolidado.csv. Muéstrame cuántas semanas quedaron por
combustible y una gráfica rápida. No toques api/, sync.py, docker/ ni scripts/.
```

Si el parser se complica con algún PDF, es válido completar a mano las semanas faltantes en el CSV y documentarlo ("curación manual de fuente externa"). Lo importante es tener la serie. Sube también `precios_mem_consolidado.csv` a `crudos/mem/`.

### 4.2 ⭐ Notebook de ingesta a bronce 🧱

```
PROMPT PARA CLAUDE CODE
Crea el notebook notebooks/01_bronce_ingesta.py en formato de notebook de Databricks
(# Databricks notebook source y # COMMAND ---------- entre celdas). Debe:
1. Instalar el paquete del repo (%pip install /Workspace/Users/<correo>/gasolina-mlops)
   usando un widget "ruta_repo".
2. Widgets: catalogo (default "workspace"), fecha_ejecucion.
3. Descargar las 3 series de FRED con requests a /Volumes/<catalogo>/g6_bronce/crudos/fred/
   con nombre <serie>_<fecha_ejecucion>.csv; si falla la descarga, imprimir un mensaje claro
   ("Sube el CSV manualmente a ...") y continuar sin tronar.
4. Registrar un inventario de bronce: tabla Delta <catalogo>.g6_bronce.inventario con
   ruta, tipo (foto|mem_pdf|fred_csv|api_log|etiquetas), tamaño, sha256, fecha_ingesta.
   Solo agregar archivos nuevos (merge por sha256).
5. Al final mostrar conteos por tipo.
Además, actualiza notebooks/README.md explicando el orden de ejecución.
```

Haz push, Pull en el Git folder y corre el notebook en Databricks.

Checklist:

- [ ] En `crudos/` hay `fotos/`, `mem/` (PDF + subsidio), `fred/` (CSV), `etiquetas/` y `api_logs/`.
- [ ] Existe la tabla `g6_bronce.inventario`.

### 4.3 ⭐ Bronce → Plata 🧱

```
PROMPT PARA CLAUDE CODE
Crea notebooks/02_plata.py (formato notebook de Databricks) que, usando el paquete gasolina:
1. Fotos: para cada foto en /Volumes/<cat>/g6_bronce/crudos/fotos/ que no esté ya procesada
   (por sha256 Y version_modelo, para que al mejorar el OCR se reprocese), correr
   extraer_precios con el motor, preprocesamiento y estrategia de ocr_config.json (si no
   existe en /Volumes/<cat>/g6_oro/artifacts/, usar los defaults del config), y guardar en
   <cat>.g6_plata.lecturas_ocr una fila por foto y combustible: sha256, archivo,
   fecha_foto, lat, lon, combustible, precio, fuente, confianza_ocr,
   validaciones (JSON string), score_confianza, motor, preproc, version_modelo,
   fecha_proceso. Usar pandas y luego spark.createDataFrame para escribir (append).
   Si extraer_precios devuelve "modo": "stub" (precios None), no escribir filas de precio
   nulo: imprimir "OCR todavía en modo stub" y seguir con MEM y FRED.
2. MEM: parsear todos los PDFs de crudos/mem/ con parsear_informe_mem, consolidar y escribir
   <cat>.g6_plata.precios_mem (overwrite) con fecha, semana_iso, combustible, precio_promedio.
   También cargar eventos_subsidio.csv si existe en crudos/mem/ a <cat>.g6_plata.subsidios.
3. FRED: leer los CSV más recientes de cada serie, limpiar ("." o vacíos -> null), convertir
   a numérico y escribir <cat>.g6_plata.exogenas_diarias (fecha, serie, valor).
4. Chequeos de calidad (data quality) al final: sin precios fuera de rango en plata, sin
   fechas nulas, sin duplicados; imprimir un resumen y lanzar excepción si algo crítico falla
   (para que el Job marque error).
```

### 4.4 ⭐ Plata → Oro 🧱

```
PROMPT PARA CLAUDE CODE
Crea notebooks/03_oro.py (formato notebook de Databricks):
1. <cat>.g6_oro.precios_estacion: precios leídos de fotos aprobados (score_confianza >= umbral
   del config), uno por fecha/estación/combustible, con columna estacion_id derivada del GPS
   redondeado a 3 decimales.
2. <cat>.g6_oro.comparacion_mem: para cada lectura de foto, el precio de referencia MEM de
   esa semana y la diferencia (Q y %). Esto mide el "spread" de la estación vs referencia.
3. <cat>.g6_oro.features_forecast: tabla semanal (semana ISO, combustible) con:
   precio_mem (target), lags 1-2-4 del precio MEM, promedio semanal de la serie FRED
   correspondiente (gasolina Gulf para super/regular, ULSD para diesel) convertida a Q/galón
   con tipo de cambio constante del config (7.7) y sus lags 1-2, WTI promedio semanal lag 1,
   dummy y monto de subsidio vigente esa semana.
4. Guardar en /Volumes/<cat>/g6_oro/artifacts/reglas.json (contrato 4.2 de
   docs/INSTRUCTIVO_GENERAL.md) los rangos válidos de precio (percentiles 1 y 99 del MEM
   ± 10 %) y la última referencia MEM por combustible, para que la API de producción los use.
5. Guardar /Volumes/<cat>/g6_oro/artifacts/historico.json (contrato 4.2): serie semanal MEM
   por combustible + precios leídos de fotos aprobados.
Las partes 1 y 2 deben correr sin tronar aunque lecturas_ocr esté vacía (OCR en modo stub).
```

Orden: primero deja funcionando MEM y FRED → `precios_mem`, `exogenas_diarias` → `features_forecast`. Cuando esté lista (hito H1, miércoles 10:00 p. m.), avisa en el chat: "`features_forecast` lista en oro". Después, cuando Modelos haga merge del OCR real, haz Pull y vuelve a correr `02_plata` y `03_oro` para que se procesen las fotos.

### 4.5 Revisar que las capas quedaron bien 🧱

```sql
%sql
SELECT combustible, COUNT(*), MIN(precio), MAX(precio), AVG(score_confianza)
FROM workspace.g6_plata.lecturas_ocr GROUP BY combustible;

SELECT * FROM workspace.g6_oro.comparacion_mem ORDER BY fecha_foto;

DESCRIBE HISTORY workspace.g6_plata.lecturas_ocr;   -- versiones (time travel) para el reporte
```

Toma capturas: sirven para el reporte (trazabilidad y versionado de datos).

Checklist H2:

- [ ] Tablas en plata (`lecturas_ocr`, `precios_mem`, `subsidios`, `exogenas_diarias`) y oro (`precios_estacion`, `comparacion_mem`, `features_forecast`).
- [ ] `reglas.json` e `historico.json` en `g6_oro/artifacts/` (reemplazan a los demo; revisa que digan `"origen": "databricks"`).
- [ ] PR a `main` con CI en verde.

### 4.6 ⭐ Job del pipeline (jueves antes de las 2:00 p. m.) 🧱

1. Jobs & Pipelines → Create → Job. Nombre: `g6_pipeline_semanal`.
2. Tareas, todas de tipo Notebook, con source Git provider (repo `gasolina-mlops`, rama `main`) y compute serverless:
   1. `ingesta` → `notebooks/01_bronce_ingesta`
   2. `plata` → `notebooks/02_plata` (depende de ingesta)
   3. `oro` → `notebooks/03_oro` (depende de plata)
   4. `forecast` → `notebooks/05_forecast` (depende de oro; ese notebook es de Modelos)
3. Schedule: semanal, lunes 7:00 a. m. (America/Guatemala), porque el MEM publica precios semanalmente.
4. Notifications: On failure, los correos de las 3 personas.
5. Run now. Captura del grafo de tareas en verde.

Si `05_forecast` todavía no está en `main`, crea el job con las 3 primeras tareas y agrega la cuarta después.

### 4.7 ⭐ Monitoreo de producción (jueves en la tarde) 🧱

Para esto necesitas los logs simulados que sube Ariela a `crudos/api_logs/` (ella avisa en el chat).

```
PROMPT PARA CLAUDE CODE
Crea notebooks/06_monitoreo.py (notebook de Databricks) que:
1. Lea todos los JSONL de /Volumes/<cat>/g6_bronce/crudos/api_logs/ (contrato 4.3 de
   docs/INSTRUCTIVO_GENERAL.md) y los escriba (merge por id de petición) en
   <cat>.g6_plata.api_predicciones. Debe funcionar con los logs simulados que sube la
   persona de Producción y, después, con los reales del servidor.
2. Calcule en <cat>.g6_oro.monitoreo_diario: peticiones por día, % con score >= umbral,
   % de cada validación fallida, latencia p50/p95, precio promedio leído por combustible,
   desviación promedio vs referencia MEM (drift de datos: si las lecturas se alejan del MEM
   más de X %, alerta), y comparación del pronóstico de la semana pasada vs el MEM real
   (error del modelo en producción).
3. Exporte /Volumes/<cat>/g6_oro/artifacts/monitoreo.json (contrato 4.2) para que la API lo
   muestre en la pestaña "Monitoreo".
4. Si alguna métrica cruza su umbral (definidos en config: ej. % score bajo > 30 %,
   desviación vs MEM > 10 %, MAE pronóstico > 2x MAE de validación), lanzar una excepción con
   un mensaje explicativo para que el Job falle y mande correo (alerta). Escribe el
   monitoreo.json ANTES de lanzar la excepción, con la alerta marcada como activa.
```

Crea el Job `g6_monitoreo_diario` (una tarea: `06_monitoreo`, diario a las 8:00, On failure a los 3 correos). Pruébalo con los logs simulados.

Este es el ciclo completo de MLOps: producción genera logs → bronce → monitoreo en oro → alerta → reentrenamiento.

### 4.8 ⭐ Dashboard de monitoreo (jueves en la noche) 🧱

1. Dashboards → Create dashboard.
2. Pestaña Data → Add data source → `g6_oro.monitoreo_diario`, `g6_oro.comparacion_mem`, `g6_oro.predicciones` y `g6_plata.precios_mem`.
3. Visualizaciones (Add a visualization):
   - Línea: precio MEM semanal por combustible + puntos de las fotos (histórico).
   - Línea: pronóstico vs real.
   - KPIs (counter): peticiones del día, % confianza alta, latencia p95.
   - Barras: validaciones que más fallan.
   - Tabla: últimas lecturas con score bajo (para revisión manual).
4. Agrega un filtro por `entorno` (local / servidor).
5. Publish. Capturas.

Si quieres ayuda con las consultas:

```
PROMPT PARA CLAUDE CODE
Dame las consultas SQL (Databricks SQL) para estas visualizaciones de un dashboard AI/BI,
usando las tablas <cat>.g6_oro.monitoreo_diario, comparacion_mem, predicciones y
<cat>.g6_plata.precios_mem: [pega la lista de la sección de dashboard]. Para cada una dime qué
tipo de gráfica elegir y qué columna va en cada eje.
```

Checklist H3:

- [ ] `g6_monitoreo_diario` corre con los logs simulados y escribe `monitoreo.json`.
- [ ] Dashboard publicado.
- [ ] Participas en el simulacro del jueves 10:00 p. m. (corres el job de monitoreo cuando Ariela te avise).

---

## 5. Viernes en la clase ▶ (tu papel)

| Minuto | Qué hacer |
| --- | --- |
| 15–30 | Ayudar con capturas de la página y de `/docs`. |
| 30–45 | Video de la demo (tú muestras la parte de Databricks: capas y dashboard). |
| 55–70 | Cuando Ariela suba los logs reales (`fin_de_clase.sh`), correr `g6_monitoreo_diario`, refrescar el dashboard y tomar capturas con `entorno = servidor`. Avisar cuando `monitoreo.json` esté actualizado. |

---

## 6. Para el reporte (después del viernes)

Tú escribes las secciones 3 (Datos), 4 (Arquitectura, parte de capas) y 8 (Monitoreo) del reporte (estructura en la sección 10.2 del general). Junta: capturas de las tablas por capa, `DESCRIBE HISTORY`, el grafo del job en verde, el dashboard y las limitaciones (formato PDF del MEM, tipo de cambio constante, curación manual si la hubo).

---

## 7. Problemas comunes

| Problema | Causa probable | Solución |
| --- | --- | --- |
| `%pip install` falla | Ruta del repo mal escrita | Clic derecho en la carpeta → Copy path. |
| `PERMISSION_DENIED` al crear esquema o volumen | Sin permisos en ese catálogo | Pedir al profesor un catálogo o esquema. |
| `requests` no descarga FRED | Internet restringido en el workspace | Usar los CSV que subiste a mano a `crudos/fred/`. |
| `02_plata` no escribe fotos | OCR todavía en modo stub | Normal hasta que Modelos haga merge. Haz Pull y vuelve a correr. |
| El job no ve tus cambios | El job usa la rama `main` | Haz el merge de tu PR a `main` primero. |
| `monitoreo.json` no aparece en la página | Ariela no ha sincronizado | Avísale para que corra `gasolina-sync descargar`. |

Para cualquier error, pégaselo a Claude Code:

```
PROMPT PARA CLAUDE CODE
Estoy en el paso [X.Y] del instructivo [general / de mi rol]. Corrí: [comando]. Me salió:
[error completo]. Estoy en [mi Mac / el servidor / Databricks]. Explícame qué significa y
dame el arreglo paso a paso.
```
