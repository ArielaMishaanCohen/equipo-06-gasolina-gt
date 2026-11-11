# Proyecto Final — ML Engineering (CC3105)

## Predicción del precio de la gasolina en Guatemala: fotos → S3 → Databricks (medallón) → API en el Droplet

Grupo 6 · Instructivo general **v3** (alineado con el enunciado oficial `cc3105_proyecto_final.pdf`)

---

## 0. Qué cambió en la v3 y cómo usar este documento

El catedrático publicó el enunciado oficial. Este instructivo lo sigue al pie de la letra y reemplaza a la v2 (guardada en `_versiones_anteriores/v2/`). Lo que ya construimos (repo, CI/CD, despliegue en el Droplet) se reutiliza casi completo.

| Tema | v2 (lo que suponíamos) | v3 (lo que pide el enunciado) |
| --- | --- | --- |
| Pregunta del modelo | Regresión: precio de la próxima semana | **Clasificación**: ¿el precio de cada combustible `sube`, `baja` o `se_mantiene` la semana siguiente? Contra la línea base "se repite la dirección de la semana anterior". |
| Fotos | Nuestras 5 fotos de una bomba Shell | Las fotos que **sube el catedrático** a `s3://<bucket-bronce>/fotos/AAAA-MM-DD/` (rótulos de gasolineras o tablas del MEM). Nuestras fotos sirven como extra. |
| Combustibles | diesel, regular, super, vpower | **super, regular, diesel** (+ modalidad y ubicación si aparecen) |
| Almacenamiento | Volúmenes administrados | **3 buckets S3 por capa**, con external locations, cada equipo en su prefijo `equipo-XX/` |
| Tablas | `g6_plata.lecturas_ocr`, `g6_oro.*` | `bronze.fotos_precios`, `silver.precios`, `silver.precios_rejected`, `gold.precio_semanal`, `gold.variacion_semanal`, `gold.features_modelo`, `gold.predicciones` (+ `gold.metricas_modelo`) |
| Semana | Semana ISO (lunes a domingo) | **Martes a lunes**, igual que el MEM |
| Orquestación | Varios notebooks y jobs | **Job con 3 tareas** Bronce → Plata → Oro en un **job cluster**, con trigger o programación, alerta por correo y 2 ejecuciones exitosas con fotos de semanas distintas |
| API | Lee JSON sincronizados; `/extraer`, `/pronostico` | **Lee las tablas Oro desde S3** (Delta con `deltalake`) con credenciales de solo lectura. Endpoints: `/health`, `/precios/actual`, `/precios`, `/prediccion`, `/modelo/metricas`, en el **puerto 80XX** |
| Entorno en el Droplet | Docker | Docker no se puede (sin sudo, y el enunciado prohíbe instalar paquetes del sistema). Usamos **uv** (`pyproject.toml` + `uv.lock`). La imagen Docker se sigue construyendo en el CI como extra. |
| Plazo | Viernes 13 | **Entrega la próxima semana** (el enunciado habla de 5 hitos semanales, pero el catedrático confirmó que se entrega la otra semana). Los 5 hitos se comprimen en días (sección 3). Presentación ante un jurado externo. |
| Entregables | Reporte libre | Repo `equipo-XX-gasolina-gt` con `docs/` (diagrama + informe de 5 páginas), `pipelines/`, `api/`, `tests/`, `presentacion/` |

Cómo leerlo:

- La sección 7 dice qué hacer **ahora mismo**. Las secciones 8 a 11 son semana por semana.
- Los bloques `PROMPT PARA CLAUDE CODE` se copian tal cual en Claude Code, abierto en la carpeta que diga el paso.
- Cada persona tiene su guía en `instructivos_equipo/`. Este documento es el mapa; la guía es la lista de tareas.

| Símbolo | Lugar |
| --- | --- |
| 💻 | Tu Mac (Terminal o Claude Code) |
| 🧱 | Databricks (navegador) |
| 🌊 | Droplet de DigitalOcean (por SSH) |
| 🐙 | GitHub (navegador) |
| ☁️ | AWS S3 (a través de Databricks) |

---

## 1. El proyecto en una página

### 1.1 Qué hay que demostrar (del enunciado)

1. Databricks conectado a buckets S3 con storage credentials y external locations de Unity Catalog.
2. Precios estructurados extraídos de fotos (OCR o modelo de visión) y validados con reglas de calidad.
3. Las tres capas medallón con tablas Delta.
4. Un modelo que predice si cada combustible sube o baja la semana siguiente, evaluado contra los precios reales.
5. Uso correcto de clusters: interactivo para desarrollar, job cluster para el pipeline automático.
6. Una API sobre la capa Oro en el Droplet, por SSH y con dependencias aisladas.
7. Documentación y presentación reproducibles por otra persona.

### 1.2 Arquitectura

```
                     ┌─────────────────────── AWS S3 (un bucket por capa) ───────────────────────┐
 Catedrático ──────► │ BRONCE  s3://cc3105-cusn-…/fotos/AAAA-MM-DD/   (solo lectura, compartido) │
 (sube fotos)        │         s3://cc3105-cusn-…/equipo-XX/          (nuestro prefijo)          │
                     │ PLATA   s3://cc3105-ag-…/equipo-XX/                                        │
                     │ ORO     s3://cc3105-au-…/equipo-XX/                                        │
                     └──────────────▲──────────────────────────────────────────▲───────────────────┘
                                    │ external locations (Unity Catalog)        │ lectura (credenciales
                     ┌──────────────┴──────────── DATABRICKS ──────────────┐    │  de solo lectura)
                     │ Job equipo-XX-pipeline (job cluster)                │    │
                     │   01_bronze ──► 02_silver ──► 03_gold               │    │
                     │   binaryFile    OCR + reglas  semanal, variación,   │    │
                     │   incremental   + cuarentena  features, modelo,     │    │
                     │                 + MERGE       predicciones          │    │
                     │ MLflow: experimentos OCR y clasificador             │    │
                     │ Cluster interactivo (desarrollo, autoterminación)   │    │
                     └─────────────────────────────────────────────────────┘    │
                                                                                 │
   Equipo ──SSH──►   ┌──────────── DROPLET DigitalOcean (159.65.111.14) ────────┴────┐
   GitHub Actions ─► │ uv + FastAPI · puerto 80XX · arranque solo (@reboot)          │
                     │ /health /precios/actual /precios /prediccion /modelo/metricas │
   Usuario ──HTTP──► │ /docs (Swagger) · página web                                   │
                     └────────────────────────────────────────────────────────────────┘
```

Los tres buckets ya existen como external locations en el workspace. Por los nombres (símbolos químicos), deducimos:

| External location | Bucket | Capa |
| --- | --- | --- |
| `xloc-raw` | `s3://cc3105-raw-869227452861-us-east-2-an/img/` | **Fotos del catedrático**. Solo lectura. Al 10 de noviembre: 38 fotos `.HEIC` (3024×4032) de **bombas** (Shell y Puma), una por semana aproximadamente, del 7 de enero al 8 de noviembre de 2026, todas con fecha y GPS en el EXIF; sin subcarpetas de fecha. Copia local en `Proyecto/datos/fotos_profesor/`. |
| `xloc-cusn` | `s3://cc3105-cusn-869227452861-us-east-2-an/` | Bronce (Cu + Sn = bronce). Ya existe una carpeta `equipo0/`: el prefijo parece ser `equipo<N>/` (confirmar). |
| `xloc-ag` | `s3://cc3105-ag-869227452861-us-east-2-an/` | Plata (Ag) |
| `xloc-au` | `s3://cc3105-au-869227452861-us-east-2-an/` | Oro (Au) |

Confírmenlo con el catedrático (sección 13).

### 1.3 Decisiones técnicas

| Decisión | Elegido | Por qué |
| --- | --- | --- |
| OCR | RapidOCR (ya en el paquete), comparado en MLflow contra EasyOCR o Tesseract | No necesita GPU ni descargar modelos; corre en el cluster y en el Droplet. Experimento opcional: un modelo de visión con `ai_query` si el workspace lo permite. |
| Código | Paquete de Python `gasolina` (en `src/`) usado por los notebooks y por la API | El mismo código en Databricks y en el Droplet. Los notebooks solo orquestan. |
| Tablas | Delta **externas** con `LOCATION` explícito en el prefijo del equipo | Así la API sabe la ruta exacta de cada tabla Oro en S3 y la lee con `deltalake`. |
| Modelo | Regresión logística y árbol de decisión vs. línea base | Lo que pide el enunciado; pocos datos semanales, así que un modelo simple y explicable. |
| Historia para el modelo | Fuente complementaria en Bronce: histórico semanal de referencia del MEM (y, opcional, petróleo WTI de FRED) | Con 5 semanas de fotos no se puede entrenar ni validar. El histórico del MEM da decenas de semanas con la misma definición de semana (martes a lunes). |
| Entorno del Droplet | uv (`pyproject.toml` + `uv.lock`) en el usuario, sin sudo | El enunciado prohíbe instalar paquetes del sistema y Docker requiere root. uv es reproducible con el lock. |
| Persistencia de la API | `nohup` + `@reboot` en crontab (lo instala `deploy.sh`) | Equivalente a un servicio: sigue corriendo al cerrar SSH y arranca solo al encender. |
| CI/CD | GitHub Actions: ruff + pytest + imagen en GHCR; deploy manual por SSH | Cuenta para los puntos extra (pruebas automatizadas y CI/CD hacia el Droplet). |

---

## 2. Datos del equipo y accesos

Llenen lo que falta en cuanto el catedrático lo confirme. **Todo lo que dice "(confirmar)" se cambia solo en `config/config.yaml` y en los widgets**, no en el código.

| Recurso | Valor |
| --- | --- |
| Número de equipo | `06` (confirmar) → `equipo-06`, `equipo_06` |
| Droplet | `159.65.111.14`, usuario `cc3105` (el enunciado dice `equipo-XX`; confirmar), carpeta `~/apps/gasolina-mlops` |
| Puerto de la API | `8006` (confirmar; el enunciado dice `80XX`). Hoy corre en 8000. |
| Workspace Databricks | `https://dbc-f51e9943-f137.cloud.databricks.com` (Free Edition: solo cómputo serverless; confirmar qué cómputo usar para el Job) |
| Catálogo y esquemas | `workspace.equipo_06_bronze`, `workspace.equipo_06_silver`, `workspace.equipo_06_gold` (confirmar; el enunciado dice "catálogo o esquemas con prefijo `equipo_XX`") |
| Fotos del catedrático | `s3://cc3105-cusn-869227452861-us-east-2-an/fotos/AAAA-MM-DD/` (confirmar) |
| Prefijos del equipo | `s3://cc3105-cusn-…/equipo-06/`, `s3://cc3105-ag-…/equipo-06/`, `s3://cc3105-au-…/equipo-06/` |
| Credenciales de solo lectura para la API | AWS (access key de solo lectura sobre el bucket Oro) — pedirlas al catedrático |
| Repo | `github.com/ArielaMishaanCohen/gasolina-mlops` → renombrar a `equipo-06-gasolina-gt` (sección 7.3) |

Reglas del enunciado que hay que cumplir siempre:

- Cada equipo trabaja **solo** en su prefijo de S3, sus esquemas, su usuario y su puerto. Tocar recursos de otro equipo es falta grave.
- Llaves SSH y credenciales: nunca en el chat, nunca en el repo. En el Droplet van en `.env` con permisos `600`.
- Cluster interactivo con **autoterminación de máximo 30 minutos**. Clusters encendidos sin uso restan puntos.
- En el Droplet: no instalar paquetes del sistema ni reiniciar sin autorización.
- Cada integrante debe poder explicar cualquier parte del código en la presentación.

---

## 3. Calendario, hitos y rúbrica

**Se entrega la próxima semana**, así que los 5 hitos del enunciado se comprimen en días. Las fechas suponen entrega el martes 17 de noviembre: confirmen el día exacto de la entrega y de la presentación con el catedrático y corran el plan si cambia. En el resto del documento y en las guías, "semana 1 … semana 5" significa estos bloques de días.

| Bloque | Cuándo | Hito del enunciado | Responsable principal |
| --- | --- | --- | --- |
| "Semana 1" | Mar 10 (noche) – Mié 11 | Acceso SSH ✅; `00_setup` corrido; fotos en `bronze.fotos_precios`; histórico del MEM en Bronce; repo reorganizado | Datos y Producción |
| "Semana 2" | Mié 11 – Jue 12 | Extracción funcionando; `silver.precios` con reglas, cuarentena y MERGE; revisión manual de 20+ fotos | Modelos y Datos |
| "Semana 3" | Vie 13 – Sáb 14 | Tablas Oro, modelo en MLflow, Job de punta a punta con 2 ejecuciones | Datos y Modelos |
| "Semana 4" | Sáb 14 (en paralelo desde el miércoles) | API en el Droplet leyendo Oro real (se construye desde el miércoles con datos de ejemplo) | Producción |
| "Semana 5" | Dom 15 – Lun 16 | README, diagrama, informe, presentación, resumen de una página (48 h antes de presentar), ensayo y predicción registrada | Todos |
| Entrega | ~Mar 17 (confirmar) | Repo final, Job compartido, API en línea, presentación ante el jurado | Todos |

Regla para cumplir el plazo: lo indispensable es lo que da puntos en la rúbrica. Lo marcado como "opcional" o "extra" se hace solo si el bloque del día ya está completo.

Rúbrica (100 puntos + 5 extra) y dónde se gana cada punto:

| Criterio | Pts | Dónde se gana |
| --- | --- | --- |
| Capa Bronce | 10 | `01_bronze`: binaryFile o Auto Loader por external location, carga incremental, `_ingestion_timestamp` y `_source_file` |
| Capa Plata | 15 | `02_silver`: extracción, 3+ reglas, `precios_rejected` con motivo, MERGE idempotente, exactitud medida a mano en 20+ fotos |
| Capa Oro | 10 | `03_gold`: semanal (martes a lunes), variación, dirección con umbral, `COMMENT` en tablas y columnas |
| Modelo | 10 | Validación temporal, comparación con la línea base, MLflow |
| Clusters y Job | 10 | Interactivo vs. job cluster documentado, Job de 3 tareas, trigger o programación, alerta por correo, 2 ejecuciones |
| API en el Droplet | 20 | Endpoints, filtros, `?limit`, entorno aislado, servicio persistente, `.env` con 600 |
| Repo y README | 10 | Diagrama, código, presentación, reproducibilidad, **commits de todos** |
| Informe técnico | 5 | `docs/informe.pdf`, máximo 5 páginas |
| Presentación y demo | 10 | Jurado externo |
| Extra | +5 | 3 por la mejor predicción de la semana 5; 2 por pruebas automatizadas de la API, CI/CD hacia el Droplet o dashboard de Databricks SQL (ya tenemos los dos primeros) |

---

## 4. Roles, dueños de archivos y flujo de Git

| Rol | Quién | Guía | Entrega |
| --- | --- | --- | --- |
| Producción y coordinación | Ariela | `1_PRODUCCION_Ariela.md` | Repo, README, API, Droplet, CI/CD, pruebas de la API, diagrama |
| Datos | Compañero 1: ________ | `2_DATOS.md` | Bronce, reglas y tablas de Plata, Oro (semanal, variación, features), Job, clusters, dashboard |
| Modelos | Compañero 2: ________ | `3_MODELOS.md` | Extracción de precios (OCR), revisión manual de 20+ fotos, experimentos, clasificador, predicciones |
| Todos | — | Sección 11 | Informe, presentación, commits propios |

Dueños de archivos (estructura nueva, sección 7.3):

| Rol | Archivos |
| --- | --- |
| Producción | `pyproject.toml`, `uv.lock`, `config/`, `api/`, `src/gasolina/api/`, `src/gasolina/oro.py` (lectura de Oro), `src/gasolina/sync.py`, `src/gasolina/config.py`, `docker/`, `scripts/`, `.github/`, `tests/test_api.py`, `tests/consultas_api.sh`, `docs/arquitectura.*`, `README.md` |
| Datos | `pipelines/00_setup.sql`, `pipelines/01_bronze.py`, `pipelines/03_gold.py` (partes de indicadores y features), `pipelines/job.json`, `src/gasolina/calidad.py`, `src/gasolina/externos.py`, `src/gasolina/features.py`, sus tests |
| Modelos | `pipelines/02_silver.py` (extracción), `src/gasolina/metadata.py`, `ocr.py`, `reglas.py`, `extraccion.py`, `modelo.py`, `pipelines/04_experimentos_ocr.py`, la parte de entrenamiento y predicción de `03_gold.py`, sus tests |

Flujo de Git (cuenta para la rúbrica: **commits de todos los integrantes**):

- Ramas `produccion`, `datos` y `modelos`. Nadie trabaja directo en `main`.
- Integrar con Pull Request a `main`; el CI tiene que estar en verde.
- Antes de cada sesión: `git checkout main && git pull && git checkout <tu-rama> && git merge main`.
- En Databricks, cada quien tiene su Git folder y hace commits desde ahí (el enunciado pide que el código de los pipelines se sincronice con Git folders).
- Nunca al repo: fotos, `.env`, llaves, credenciales.

---

## 5. Contratos entre roles (obligatorios)

Si alguien necesita cambiar un contrato, lo avisa en el chat y se actualiza aquí **antes** de tocar código.

### 5.1 `bronze.fotos_precios`

| Columna | Tipo | Nota |
| --- | --- | --- |
| `path` | STRING | Ruta completa en S3 (llave natural) |
| `modificationTime` | TIMESTAMP | De binaryFile |
| `length` | BIGINT | Bytes |
| `content` | BINARY | La foto |
| `fecha_carpeta` | DATE | De `fotos/AAAA-MM-DD/` |
| `_ingestion_timestamp` | TIMESTAMP | Hora de la carga |
| `_source_file` | STRING | Ruta de la foto de origen |

Fuente complementaria (opcional pero muy recomendada): `bronze.mem_referencia_raw` (CSV o PDF del MEM tal cual) y `bronze.fred_raw` (WTI).

### 5.2 Salida de `extraer_precios` (Modelos la produce; `02_silver` la consume)

Una llamada por foto. Devuelve un dict; **ninguna clave se omite** (lo que no se lea va como `null`):

```json
{
  "archivo": "IMG_0001.jpg",
  "modo": "real",
  "metadata": {"archivo": "IMG_0001.jpg", "fecha_hora": "2026-11-10T08:12:33", "lat": 14.56,
               "lon": -90.46, "altitud": null, "modelo_camara": null, "ancho": 4032, "alto": 3024,
               "sha256": "…"},
  "registros": [
    {"combustible": "super", "precio_q_galon": 33.45, "modalidad": "autoservicio",
     "ubicacion": "Shell Km 14", "confianza": 0.91, "texto_fuente": "SUPER 33.45"}
  ],
  "tipo_foto": "rotulo",
  "validaciones": [{"nombre": "formato_y_rango", "estado": "ok", "mensaje": "…"}],
  "score_confianza": 0.88,
  "motor": "rapidocr",
  "preproc": "gris_clahe",
  "tiempo_ms": 850,
  "version_modelo": "0.2.0",
  "detecciones_crudas": []
}
```

- `combustible` ∈ {`super`, `regular`, `diesel`}. `modalidad` ∈ {`autoservicio`, `servicio_completo`, `null`}.
- `tipo_foto` ∈ {`rotulo`, `bomba`, `tabla_mem`, `desconocido`}.
- `modo`: `"stub"` mientras no exista el OCR real (`registros` vacío).

### 5.3 `silver.precios` y `silver.precios_rejected`

`silver.precios` (llave: `fecha + ubicacion + combustible + modalidad`, cargada con `MERGE`):

| Columna | Tipo |
| --- | --- |
| `fecha` | DATE (de la carpeta o del EXIF) |
| `combustible` | STRING (`super`, `regular`, `diesel`) |
| `precio_q_galon` | DECIMAL(6,2) |
| `modalidad` | STRING (`autoservicio`, `servicio_completo` o `no_indica`) |
| `ubicacion` | STRING (o `no_indica`) |
| `foto_origen` | STRING (ruta en Bronce) |
| `confianza` | DOUBLE |
| `motor`, `version_modelo` | STRING |
| `_procesado_en` | TIMESTAMP |

`modalidad` y `ubicacion` nunca son `null` en Plata (se usa `no_indica`), para que la llave del MERGE funcione.

`silver.precios_rejected`: mismas columnas + `motivo` (STRING) + `regla` (STRING). Una foto sin ningún precio legible también va aquí (con `combustible = null` y `motivo = "sin_precios_legibles"`).

Reglas de calidad (mínimo 3, implementadas en `src/gasolina/calidad.py`):

| Regla | Condición | Justificación |
| --- | --- | --- |
| `rango_precio` | 20 ≤ precio ≤ 60 Q/gal | Rango histórico del MEM 2020–2026 con margen |
| `combustible_valido` | combustible ∈ catálogo | El modelo solo conoce 3 combustibles |
| `fecha_no_futura` | fecha ≤ hoy | Una fecha futura es un error de metadata |
| `consistencia_gasolinas` (extra) | super > regular en la misma foto | Siempre se cumple en Guatemala |
| `confianza_minima` (extra) | confianza ≥ 0.5 | Lecturas dudosas a revisión |

### 5.4 Tablas Oro (Datos y Modelos las producen; la API las lee de S3)

Todas son Delta **externas** en `s3://cc3105-au-…/equipo-06/gold/<tabla>/`, con `COMMENT` en la tabla y en cada columna.

| Tabla | Columnas |
| --- | --- |
| `gold.precio_semanal` | `semana_inicio` DATE (martes), `semana_fin` DATE (lunes), `combustible`, `precio_promedio`, `precio_min`, `precio_max`, `n_registros`, `fuente` (`fotos` o `mem`) |
| `gold.variacion_semanal` | `semana_inicio`, `combustible`, `precio_promedio`, `precio_anterior`, `dif_q`, `dif_pct`, `direccion` (`sube`, `baja`, `se_mantiene`), `umbral_q` |
| `gold.features_modelo` | `semana_inicio`, `combustible`, `var_q_1`, `var_q_2`, `var_q_3`, `var_q_4`, `prom_movil_4`, `dif_super_diesel`, `direccion_actual`, `wti_var_1` (opcional), `subsidio_activo` (opcional), `direccion_siguiente` (objetivo; `null` en la última semana) |
| `gold.predicciones` | `semana_objetivo` DATE (martes de la semana predicha), `combustible`, `prediccion`, `probabilidad`, `prediccion_baseline`, `modelo`, `version_modelo`, `mlflow_run_id`, `fecha_generacion` TIMESTAMP, `direccion_real` (se llena cuando se conoce) |
| `gold.metricas_modelo` | `fecha_entrenamiento`, `modelo`, `version_modelo`, `accuracy_modelo`, `accuracy_baseline`, `f1_macro_modelo`, `f1_macro_baseline`, `n_semanas_test`, `supera_baseline` BOOLEAN, `mlflow_run_id`, `es_champion` BOOLEAN |

Definiciones (iguales en todos los notebooks y en el informe):

- Semana: de martes a lunes. `semana_inicio = fecha - ((dayofweek(fecha) - 3 + 7) % 7)` días (en Spark, `dayofweek` da 1 = domingo y 3 = martes).
- `direccion`: `sube` si `dif_q > umbral_q`, `baja` si `dif_q < -umbral_q` y, si no, `se_mantiene`. `umbral_q = 0.10` (widget).
- Línea base: la dirección de la semana siguiente es igual a la de la semana actual.

### 5.5 Respuestas de la API (Producción las produce; la demo y las pruebas las consumen)

| Endpoint | Respuesta |
| --- | --- |
| `GET /health` | `{"status": "ok", "version", "fuente_oro": "s3"\|"demo", "tablas": {nombre: {"filas", "ultima_semana"}}, "hora_servidor"}` |
| `GET /precios/actual` | `{"semana_inicio", "precios": [{"combustible", "precio_promedio", "precio_min", "precio_max", "fuente"}]}` |
| `GET /precios?combustible=diesel&desde=2026-10-01&hasta=2026-11-30&limit=100&offset=0` | `{"total", "limit", "offset", "datos": [filas de precio_semanal + variación]}` |
| `GET /prediccion?combustible=super` | `{"semana": "2026-11-17", "combustible": "super", "prediccion": "sube", "probabilidad": 0.68, "modelo", "prediccion_baseline"}` (sin `combustible`: lista con los 3) |
| `GET /modelo/metricas` | `{"modelo", "version_modelo", "accuracy_modelo", "accuracy_baseline", "f1_macro_modelo", "f1_macro_baseline", "supera_baseline", "n_semanas_test", "fecha_entrenamiento"}` |

Errores: `400` con mensaje en español si un filtro es inválido; `404` si el combustible no existe.

---

## 6. Lo que ya está hecho (al 10 de noviembre)

- [x] Repo con el paquete `gasolina`, API mínima, Docker, scripts y tests (21 pruebas) en GitHub.
- [x] CI en verde: ruff + pytest + imagen `ghcr.io/arielamishaancohen/gasolina-mlops` (pública).
- [x] Deploy manual desde GitHub Actions (`deploy`) por SSH, en verde.
- [x] Droplet: API corriendo en modo venv con uv, `/health` responde desde internet en el puerto 8000, `@reboot` en crontab y cron horario de subida de logs.
- [x] Sincronización con Databricks probada (token personal).
- [ ] La API todavía expone los endpoints de la v2. Se rehace en la semana 4 (y se adelanta con datos de ejemplo en la semana 1).

---

## 7. Semana 1 — Ahora mismo (el catedrático ya dio permisos de lectura y escritura)

### 7.1 ⭐ Preguntarle al catedrático (Ariela, hoy)

Lista completa en la sección 13. Lo indispensable: número de equipo, puerto, nombres de catálogo y esquemas, ruta de las fotos, credenciales de solo lectura de S3 para la API, y qué cómputo usar para el Job.

### 7.2 ⭐ Ver qué se puede leer ya en S3 🧱 (cualquiera, 5 minutos)

En un notebook (o en el SQL Editor):

```sql
%sql
LIST 's3://cc3105-cusn-869227452861-us-east-2-an/';
LIST 's3://cc3105-cusn-869227452861-us-east-2-an/fotos/';
SHOW GRANTS ON EXTERNAL LOCATION `xloc-cusn`;
```

- Si `LIST` funciona y aparecen carpetas `AAAA-MM-DD/`, ya podemos leer las fotos: Datos puede desarrollar `01_bronze` en modo lectura.
- Si sale `PERMISSION_DENIED`, todavía no hay permisos de lectura: se avisa al catedrático y se sigue con 7.3 a 7.5.

### 7.3 ⭐ Reorganizar el repo a la estructura del enunciado 💻 (Ariela)

```
PROMPT PARA CLAUDE CODE
Estoy en Proyecto/gasolina-mlops. Lee ../INSTRUCTIVO_GENERAL.md (v3), secciones 1, 2, 4 y 5,
y el enunciado ../cc3105_proyecto_final.pdf. Reorganiza el repo a la estructura que pide el
enunciado SIN romper lo que ya funciona (CI, deploy.sh, Droplet):
1. notebooks/ -> pipelines/ (01_bronze.py, 02_silver.py, 03_gold.py como notebooks de
   Databricks con widgets, todavía en esqueleto con TODOs claros por rol; 00_setup.sql con
   esquemas y tablas externas en los prefijos equipo-06 de los 3 buckets; job.json de ejemplo).
2. api/: README.md, .env.example (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION,
   ORO_S3_PREFIX, PUERTO) y un main.py delgado que importe la app del paquete; el código sigue
   en src/gasolina/api/.
3. docs/: mueve los instructivos a docs/instructivos/, deja docs/arquitectura.drawio vacío y
   docs/README.md con lo que falta (informe.pdf, arquitectura.png).
4. presentacion/README.md y tests/consultas_api.sh (curl de todos los endpoints de la sección
   5.5, con BASE_URL configurable).
5. Actualiza config/config.yaml con la sección 2 del instructivo (equipo, puerto 8006, buckets,
   esquemas, umbral_q 0.10, semana martes-lunes) y el contrato 5.2 en extraccion.py (stub) y en
   tests/test_contratos.py. Quita lo de la v2 que ya no aplica (vpower, forecast regresión,
   artifacts JSON) o márcalo como plan B.
6. Agrega uv.lock (uv lock) y haz que scripts/deploy.sh en modo venv use "uv sync --extra api"
   cuando exista uv.lock. Puerto configurable con PUERTO en .env (default 8006).
7. README.md nuevo con: problema, arquitectura, cómo reproducir el pipeline, cómo desplegar la
   API, justificación del entorno (uv, por qué no Docker en el Droplet), enlaces a docs/ y
   presentacion/.
Corre ruff y pytest al final y muéstrame un resumen.
```

Después, en GitHub 🐙: Settings → General → Repository name → `equipo-06-gasolina-gt` → Rename. GitHub redirige la URL vieja, pero actualicen el remoto: en la Mac `git remote set-url origin https://github.com/ArielaMishaanCohen/equipo-06-gasolina-gt.git` y en el Droplet lo mismo dentro de `~/apps/gasolina-mlops`. Agreguen a los compañeros como colaboradores (Settings → Collaborators) y al catedrático si el repo fuera privado.

### 7.4 ⭐ API con datos de ejemplo 💻 (Ariela)

La API ya se puede construir completa sin esperar a Datos y Modelos: se generan tablas Oro de ejemplo con el contrato 5.4 en `artifacts_demo/oro/` (Delta local con `deltalake`) y la API las lee igual que leerá las de S3. Prompt en la guía de Producción (sección 3.2).

### 7.5 ⭐ Fuente complementaria y etiquetas (Datos y Modelos)

- Datos: conseguir el **histórico semanal de precios de referencia del MEM** (mínimo desde enero de 2025) para super, regular y diésel, en CSV. Es la historia que va a permitir entrenar y validar el modelo. Guía de Datos, sección 3.3.
- Modelos: preparar la plantilla de revisión manual (`etiquetas.csv`) y adaptar el OCR a fotos genéricas (rótulos y tablas del MEM, no solo bombas Shell). Guía de Modelos, sección 3.

### 7.6 ⭐ Esquemas, tablas y Bronce 🧱 (Datos, hoy en la noche o mañana temprano)

Ya hay permisos: correr `pipelines/00_setup.sql` (esquemas + tablas externas) y luego `01_bronze` → hito: primeras fotos en `bronze.fotos_precios`. Si el repo reorganizado todavía no está, el SQL de la guía de Datos (sección 3.2) se puede correr directo en un notebook.

Checklist de la semana 1:

- [x] SSH al Droplet verificado.
- [ ] Respuestas del catedrático anotadas en la sección 2.
- [ ] Repo reorganizado y renombrado; compañeros como colaboradores.
- [ ] `bronze.fotos_precios` con las fotos del catedrático; una segunda carga no duplica.
- [ ] Histórico del MEM en Bronce.

---

## 8. Semana 2 — Plata: extracción y reglas de calidad

| Quién | Qué | Guía |
| --- | --- | --- |
| Modelos | `extraer_precios` real (contrato 5.2) y `pipelines/02_silver.py` | Modelos 4.1–4.3 |
| Datos | `calidad.py` (reglas), `silver.precios_rejected`, MERGE idempotente; MEM a Plata | Datos 4.1–4.2 |
| Modelos | Revisión manual de 20+ fotos y % de precios correctos | Modelos 4.4 |
| Producción | API leyendo las tablas de ejemplo con todos los endpoints y pruebas | Producción 3.2–3.3 |

Criterio de aceptación: el notebook muestra cuántas fotos se procesaron, cuántas se rechazaron y por qué, y la exactitud de la revisión manual; una segunda ejecución produce el mismo resultado (mismo conteo de filas).

---

## 9. Semana 3 — Oro, modelo y Job

| Quién | Qué | Guía |
| --- | --- | --- |
| Datos | `gold.precio_semanal`, `gold.variacion_semanal`, `gold.features_modelo` con `COMMENT` | Datos 5.1 |
| Modelos | Clasificador vs. línea base con validación temporal en MLflow; `gold.predicciones` y `gold.metricas_modelo` | Modelos 5.1–5.2 |
| Datos | Job `equipo-06-pipeline` (3 tareas, job cluster, trigger, correo) y 2 ejecuciones con fotos de semanas distintas | Datos 5.2–5.3 |
| Datos | Documentar el cluster interactivo (runtime, nodo, workers, autoterminación ≤ 30 min, librerías) | Datos 5.4 |
| Producción | Exportar `job.json` al repo; pedir credenciales de solo lectura | Producción 4 |

Criterio de aceptación: el catedrático hace "Run now" y las tablas Oro se actualizan sin tocar ningún notebook.

---

## 10. Semana 4 — API final en el Droplet

| Quién | Qué |
| --- | --- |
| Producción | `.env` del Droplet con las credenciales de solo lectura (chmod 600), puerto 80XX, `bash scripts/deploy.sh` o el workflow `deploy`; `/health` con `fuente_oro: s3` |
| Producción | `tests/consultas_api.sh` contra la IP pública: precio actual y predicción de super, regular y diésel |
| Todos | Probar desde sus computadoras: `curl http://159.65.111.14:80XX/health` |

Criterio de aceptación: desde una computadora externa, `/health` responde y cada endpoint devuelve datos de la capa Oro (no de ejemplo).

---

## 11. Semana 5 — Entregables y presentación

### 11.1 Lista de entregables

En GitHub (`equipo-06-gasolina-gt`):

- [ ] `docs/arquitectura.png` + `docs/arquitectura.drawio` (o `.excalidraw`): buckets por capa, workspace con clusters y Job, Droplet con la API, flujos SSH y HTTP.
- [ ] `pipelines/` con `01_bronze.py`, `02_silver.py`, `03_gold.py` y `job.json` exportado (sincronizados con Git folders).
- [ ] `api/` con su entorno (`pyproject.toml` + `uv.lock`) y `.env.example` sin valores.
- [ ] `tests/consultas_api.sh`.
- [ ] `presentacion/presentacion_jurado.pdf` y `presentacion/resumen_jurado.pdf` (una página).
- [ ] `README.md` con descripción, cómo reproducir el pipeline, cómo desplegar la API y enlaces.
- [ ] `docs/informe.pdf` (máximo 5 páginas).
- [ ] Commits de **todos** los integrantes; `.gitignore` con `.env`, llaves y credenciales.

Fuera de GitHub:

- [ ] Job `equipo-06-pipeline` compartido con el catedrático, con su experimento de MLflow.
- [ ] API en línea en `http://159.65.111.14:80XX` hasta la fecha de calificación.
- [ ] Predicción de la semana siguiente registrada (puntos extra por la mejor predicción).

### 11.2 Informe técnico (máximo 5 páginas)

1. Problema y arquitectura (media página + diagrama).
2. Calidad de la extracción: método, reglas, % de rechazo y exactitud de la revisión manual (20+ fotos), ejemplos de errores.
3. Variables del modelo y por qué.
4. Resultados contra la línea base (validación temporal; tabla de accuracy y F1) y limitaciones.
5. Configuración de clusters: interactivo vs. job cluster, costo y propósito.
6. API y despliegue: entorno (uv), persistencia, credenciales, CI/CD.
7. Lecciones aprendidas.

```
PROMPT PARA CLAUDE CODE
Con base en el repo equipo-06-gasolina-gt (README, pipelines, config) y los resultados que
pego abajo, redacta docs/informe.md en español formal con ortografía perfecta, máximo 5 páginas
al exportar a PDF, con esta estructura: [pega 11.2]. Encabezado: "Equipo 06 — [nombres]".
Usa tablas para métricas y deja marcadores [CAPTURA: ...]. Resultados: [pega métricas de
MLflow, exactitud de la revisión manual, conteos de Plata y duración de las tareas del Job].
```

### 11.3 Presentación ante el jurado (20 minutos: 10 de exposición, 5 de demo, 5 de preguntas)

El jurado no conoce el curso. Orden: problema (1–2 min) → arquitectura sin jerga → de la foto al dato (% de aciertos) → el modelo frente a la línea base → demo en vivo (Job con fotos nuevas y `/prediccion`, con un **código QR** a la URL para que el jurado consulte desde su teléfono) → lecciones aprendidas.

- Todos los integrantes hablan; el jurado le puede preguntar a cualquiera.
- **48 horas antes**: entregar el resumen de una página (problema, arquitectura, resultados, URL).
- Plan B: grabación corta de la demo y capturas.

---

## 12. Problemas comunes

| Problema | Causa probable | Solución |
| --- | --- | --- |
| `PERMISSION_DENIED` en `LIST 's3://…'` | Aún sin permisos sobre la external location | Esperar al catedrático; mientras, trabajar con las 5 fotos locales y datos de ejemplo. |
| `User cannot write to a read-only external location` | La external location está marcada como solo lectura (aunque tenga el grant WRITE FILES) | Solo el catedrático lo cambia (Edit → desmarcar read only). Mientras, crear las tablas como administradas en `workspace` y cambiar a `LOCATION` en S3 después. |
| Las fotos son `.HEIC` y Pillow no las abre | Falta registrar `pillow_heif` | `pillow_heif.register_heif_opener()` antes de `Image.open` (ya es dependencia del paquete). |
| `PERMISSION_DENIED` al crear tabla con `LOCATION` | Falta `CREATE EXTERNAL TABLE` en la external location | Pedirlo al catedrático para el prefijo `equipo-06/`. |
| Auto Loader se queja del checkpoint | Checkpoint fuera del prefijo del equipo | Usar `s3://cc3105-cusn-…/equipo-06/_checkpoints/fotos/`. |
| `%pip install` falla en el cluster | Ruta del repo mal escrita | Copy path de la carpeta del Git folder. |
| El MERGE duplica filas | `modalidad` o `ubicacion` en `null` | Rellenar con `no_indica` antes del MERGE (contrato 5.3). |
| La API dice `fuente_oro: demo` | Faltan credenciales o la ruta S3 está mal | Revisar `.env` (AWS_*, ORO_S3_PREFIX) y que las tablas Oro existan. |
| `Permission denied (publickey)` | La llave no está en el Droplet | `ssh -i` con la llave correcta; revisar `~/.ssh/authorized_keys`. |
| `No module named 'gasolina'` en la Mac | macOS marcó como ocultos los archivos del `.venv` | `chflags -R nohidden .venv` |
| La API no responde desde fuera | Puerto distinto o cerrado | Confirmar el puerto 80XX; probar `curl localhost:80XX/health` en el Droplet. |

Para cualquier error:

```
PROMPT PARA CLAUDE CODE
Estoy en el paso [X.Y] del instructivo [general / de mi rol]. Corrí: [comando]. Me salió:
[error completo]. Estoy en [mi Mac / el Droplet / Databricks]. Explícame qué significa y
dame el arreglo paso a paso.
```

---

## 13. Preguntas para el catedrático

1. ¿Cuál es nuestro número de equipo? ¿Nuestro puerto es el `80XX` correspondiente? ¿Seguimos con el usuario `cc3105` o nos dará `equipo-XX`?
2. ¿Los buckets son `xloc-cusn` = Bronce, `xloc-ag` = Plata y `xloc-au` = Oro? ¿Las fotos están en `s3://cc3105-cusn-…/fotos/AAAA-MM-DD/`?
3. ✅ Ya dio permisos de lectura y escritura. Confirmar que incluyen `CREATE EXTERNAL TABLE` (para tablas con `LOCATION`) y que nuestro prefijo es `equipo-06/`.
4. ¿Usamos el catálogo `workspace` con esquemas `equipo_06_bronze`, `equipo_06_silver` y `equipo_06_gold`, o un catálogo `equipo_06` con esquemas `bronze`, `silver` y `gold`?
5. El workspace es Free Edition (solo serverless). ¿Qué cómputo usamos para el "cluster interactivo" y para el "job cluster"?
6. ¿Nos dará credenciales AWS de solo lectura para que la API lea la capa Oro desde el Droplet?
7. Como Docker no se puede instalar en el Droplet, ¿acepta uv (`pyproject.toml` + `uv.lock`) como entorno aislado?
8. ¿El Droplet quedará encendido de forma permanente hasta la fecha de calificación?
9. ¿Qué día exacto es la entrega y la presentación ante el jurado? ¿El hito "2 ejecuciones del Job con fotos de semanas distintas" se puede cumplir con las carpetas de fechas que ya hay?

---

### Fuentes

- Enunciado: `cc3105_proyecto_final.pdf`.
- MEM, precios de referencia de combustibles: https://mem.gob.gt/que-hacemos/hidrocarburos/comercializacion-downstream/precios-combustible-nacionales/
- FRED, petróleo WTI (DCOILWTICO): https://fred.stlouisfed.org/series/DCOILWTICO
- Databricks: Auto Loader con `binaryFile`, external locations y tablas externas en Unity Catalog; limitaciones de Free Edition: https://docs.databricks.com/aws/en/getting-started/free-edition-limitations
