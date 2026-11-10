# Proyecto Final — ML Engineering (CC3105)

## Lectura de precios de gasolina desde fotos + pronóstico, con arquitectura medallion y despliegue productivo

Grupo 6 · Instructivo general v2 (servidor encendido solo en clase)

---

## 0. Qué cambió y cómo usar este documento

Este instructivo reemplaza a `INSTRUCTIVO_PROYECTO_FINAL.md`. Tiene todo lo del anterior, pero reordenado alrededor de una restricción nueva: el profesor solo enciende el servidor de DigitalOcean durante la clase, y probablemente las últimas veces sean hoy (martes 10 de noviembre, 1:30 h) y el viernes 13 (1:30 h). Por eso todo se divide en dos tipos de trabajo:

| Símbolo | Tipo de trabajo                                                                 |
| ------- | ------------------------------------------------------------------------------- |
| ⏸       | Servidor apagado: se prepara, se programa y se prueba en la Mac y en Databricks. |
| ▶       | Servidor encendido: solo se corren cosas que ya están listas y probadas.        |

La regla de oro: en las ventanas ▶ no se programa nada. Solo se ejecuta, se verifica y se toman evidencias. Todo lo que se corre en el servidor ya tiene que haber corrido antes en la Mac con Docker (el mismo contenedor que va al servidor).

Cómo leerlo:

- Síguelo en orden. Cada sección dice qué haces, dónde lo haces y cómo sabes que quedó bien.
- Los bloques que empiezan con `PROMPT PARA CLAUDE CODE` se copian tal cual en Claude Code, abierto en la carpeta `Proyecto` (o en la carpeta que diga el paso).
- Los bloques `bash` se pegan en la Terminal. Fíjate siempre si dice "en tu Mac" o "en el servidor".
- Cuando algo falle, usa el prompt de errores de la sección 11.
- Las casillas `[ ]` son el checklist.
- Cada persona del equipo tiene además su propio instructivo en `instructivos_equipo/`. Este documento es el mapa completo; el de cada persona es su lista de tareas detallada.

Símbolos de dónde se hace cada cosa:

| Símbolo | Lugar                              |
| ------- | ---------------------------------- |
| 💻      | Tu Mac (Terminal o Claude Code)    |
| 🧱      | Databricks (navegador)             |
| 🌊      | Servidor de DigitalOcean (por SSH) |
| 🐙      | GitHub (navegador)                 |

Seguridad: el instructivo viejo tiene el token de Databricks pegado en el texto. No lo compartan ni lo suban a GitHub. Lo ideal es borrarlo de ese archivo y, como ya estuvo en un documento, generar uno nuevo antes del viernes (sección 6.5).

---

## 1. La idea del proyecto en una página

### 1.1 Qué problema resolvemos

Los precios de combustible están "atrapados" en fotos de bombas Shell. Queremos:

1. Leerlos automáticamente: dada una foto, devolver los precios de Diesel, Regular, Super y V-Power.
2. Validarlos con tres fuentes: la imagen misma, su metadata (fecha y GPS) y una fuente externa (precios de referencia del MEM).
3. Construir un histórico y pronosticar el precio de la próxima semana usando variables exógenas (precio internacional de gasolina y petróleo, subsidio).
4. Ponerlo en producción como una API en el servidor de DigitalOcean, con monitoreo.

### 1.2 Lo que ya sabemos de los datos (revisado en las 5 fotos)

| Hallazgo | Cómo lo usamos |
| --- | --- |
| Las 5 fotos (`IMG_8271`…`IMG_8325`) son de la misma bomba Shell (GPS ≈ 14.5600 N, −90.4628 W), tomadas el 9, 15, 22, 26 y 30 de julio de 2026 con un iPhone 14. | La fecha y el GPS de la metadata EXIF identifican la estación y la semana, sin que nadie tenga que escribirlas. |
| Los 4 precios están en 4 pantallitas, de izquierda a derecha: Diesel, Regular (FuelSave), Super (FuelSave) y V-Power. | Ordenar lo que lea el OCR por posición horizontal nos dice qué combustible es cada número. |
| En las fotos revisadas: Super = Regular + Q1.00 y V-Power = Super + Q0.50 (ej. 37.09 / 38.09 / 38.59). | Reglas de consistencia para detectar lecturas malas. Hay que confirmarlas con las 5 fotos. |
| La pantalla "Esta Venta" muestra Q150.00 y los galones. 150 ÷ 3.938 = 38.09, el precio de Super. | Es una segunda forma de obtener el precio (ruta de arriba), independiente de las pantallitas (ruta de abajo). El profesor dijo que se puede usar una, la otra o ambas. Usamos ambas y las fusionamos (ver 1.5). |
| Entre el 9 y el 26 de julio los precios suben unos Q4. | Coincide con cambios en el subsidio ("Apoyo Social Temporal", desde el 28/04/2026: Q5 en gasolinas y Q8 en diésel). Es una variable exógena clave para el pronóstico. |

### 1.3 Arquitectura (la del diagrama del profesor, aterrizada)

```
                ┌────────────────────────── DATABRICKS (laboratorio) ──────────────────────────┐
 Fotos  ───►  BRONCE                    PLATA                         ORO                       │
 MEM PDFs ─►  (crudo, tal cual)   ───►  (limpio, estructurado)  ───►  (listo para consumir)     │
 FRED CSV ─►  fotos/, mem/, fred/,      lecturas_ocr, precios_mem,    precios_historicos,       │
 API logs ─►  api_logs/                 exogenas                      features_forecast,        │
              │                                                       predicciones, métricas,   │
              │        MLflow: experimentos OCR + modelo de pronóstico  artifacts/ (modelo+config)│
              │        Jobs programados + Dashboard de monitoreo                                 │
              └───────────────────────────────────────────────────────────────┬──────────────────┘
                                                                              │ (sync de artifacts)
                                                                              ▼
                                    ┌──────── SERVIDOR DIGITALOCEAN (producción) ────────┐
   Usuario final ──HTTP──►          │  Docker → FastAPI                                  │
   (página HTML / curl)             │   POST /extraer  (foto → 4 precios + validación)  │
                                    │   GET  /pronostico                                 │
                                    │   GET  /health                                     │
   Equipo ──SSH──►                  │  logs de cada predicción → se suben a BRONCE      │
                                    └────────────────────────────────────────────────────┘
```

Las capas viven en Unity Catalog Volumes (`/Volumes/<catálogo>/<esquema>/<volumen>`). Si el profesor les da un bucket de S3 con external location, los volúmenes se crean como external volumes sobre S3 y el código no cambia, porque solo cambia una ruta en la configuración. Así el proyecto funciona en los dos escenarios.

Cómo encaja la restricción del servidor: Databricks está disponible siempre, así que todo el laboratorio (capas, MLflow, jobs, dashboard) se hace con el servidor apagado. La imagen de Docker la construye GitHub Actions y queda publicada en GitHub (GHCR); el servidor solo la descarga y la corre. Como el contenedor tiene `restart: unless-stopped`, la API se levanta sola cada vez que el profesor enciende el servidor.

### 1.4 Decisiones técnicas (y por qué)

| Decisión | Elegido | Por qué |
| --- | --- | --- |
| Motor de OCR principal | RapidOCR (`rapidocr_onnxruntime`) | Usa los modelos de PaddleOCR en formato ONNX, no necesita PyTorch ni GPU, pesa poco y los modelos vienen dentro del paquete (no descarga nada de internet, lo cual importa porque Databricks puede restringir internet). Corre bien en un servidor chico. |
| OCR para comparar | EasyOCR | Para el experimento en MLflow: "comparamos dos motores y elegimos con datos". |
| Lógica de extracción | OCR + reglas (formato, posición, rangos, consistencia, metadata, MEM) | Con 5 fotos no se puede entrenar un modelo de visión propio. Un modelo preentrenado + reglas validadas es lo profesional. |
| Pronóstico | Regresión con rezagos (baseline ingenuo vs Ridge vs Gradient Boosting) | Pocos datos semanales, así que conviene un modelo simple, explicable y comparado contra un baseline. |
| Variables exógenas | MEM (precio de referencia semanal, Ciudad de Guatemala), FRED (gasolina Gulf Coast, diésel Gulf Coast, WTI), dummy del subsidio | Guatemala importa combustible y su precio sigue al de la Costa del Golfo de EE. UU. con rezago. |
| Tracking | MLflow de Databricks | Ya viene integrado y lo vieron en el Taller 3. |
| Código | Un paquete de Python (`gasolina`) con entrypoints | Lo vieron en la Actividad 9. El mismo código corre en Databricks y en el servidor. |
| Producción | Docker + FastAPI en el droplet, imagen construida por GitHub Actions | Lo vieron en la Actividad 4. Es reproducible, y construir la imagen fuera del servidor ahorra minutos valiosos de la ventana de clase. Además, GitHub construye para `linux/amd64`, que es la arquitectura del droplet (una Mac con chip M construye `arm64`, que no corre ahí). |
| Interfaz | Página HTML servida por la misma API | Es el "plus" para que quede chilero, y Claude Code la hace rápido. |

### 1.5 Las dos rutas para leer el precio (y por qué usar ambas)

El profesor indicó que el precio se puede sacar de la parte de arriba, de la de abajo o de ambas. Este es el corazón del modelo:

| Ruta | De dónde sale | Qué da | Fortaleza | Debilidad |
| --- | --- | --- | --- | --- |
| A — Arriba ("Esta Venta") | Pantalla grande: total en Q y galones. Precio = total ÷ galones. | Un precio: el del combustible que se despachó. | Dígitos grandes, fáciles de leer. La división es exacta (150 ÷ 3.938 = 38.09). | No dice qué combustible fue, y solo da uno de los 4. |
| B — Abajo (pantallitas) | 4 pantallas "Precio por galón". | Los 4 precios, identificados por posición. | Cubre los 4 combustibles. | Dígitos pequeños de 7 segmentos, con más riesgo de error de OCR. |
| Fusión (A + B) | Ambas. | Los 4 precios + verificación cruzada. | La ruta A confirma (o corrige) uno de los precios de B e identifica qué combustible se despachó. Las reglas (Super = Regular + 1.00, V-Power = Super + 0.50) propagan la corrección a los demás. | Más lógica, pero es justo lo que da puntos. |

Cómo funciona la fusión, paso a paso:

1. Leer arriba → total y galones → `precio_A = total / galones` (redondeado a 2 decimales).
2. Leer abajo → `diesel_B, regular_B, super_B, vpower_B`.
3. Buscar cuál de los 4 precios de B está a ≤ Q0.02 de `precio_A`. Ese es el combustible despachado (`combustible_despachado`) y queda verificado por dos fuentes.
4. Si ninguno coincide pero `precio_A` coincide con lo que dan las reglas (ej. `regular_B + 1.00`), se corrige el precio de B mal leído y se marca como "corregido_por_ruta_A".
5. Si B falló y solo hay A, se reconstruyen los demás con las reglas, marcados como "inferido".
6. Cada precio final lleva su fuente (`ruta_A`, `ruta_B`, `ambas`, `corregido_por_ruta_A`, `inferido`) y entra al score de confianza.

En MLflow se comparan las tres estrategias (solo A, solo B y fusión) como un parámetro más del experimento. Esa tabla es uno de los mejores resultados para el reporte, porque demuestra con números por qué combinar fuentes funciona mejor.

---

## 2. Calendario con el servidor solo en clase

| Fase | Cuándo | Servidor | Meta | Sección |
| --- | --- | --- | --- | --- |
| Fase 0 | Hoy, antes de la clase | ⏸ | Repo base en GitHub con una API mínima que ya funciona en Docker; imagen publicada; todo lo que se va a pegar en el servidor, preparado. | 6 |
| Fase 1 | Hoy, en la clase (1:30 h) | ▶ | Infraestructura probada de punta a punta con la API mínima: SSH, Docker, puerto, sync con Databricks, deploy automático y arranque solo al encender. | 7 |
| Fase 2 | Martes noche → jueves noche | ⏸ | Todo el desarrollo real en paralelo (OCR, capas, MLflow, pronóstico, API completa, página, monitoreo), y un simulacro completo en la Mac. | 8 |
| Fase 3 | Viernes, en la clase (1:30 h) | ▶ | Despliegue final, tráfico real, evidencias, video de la demo y ciclo de monitoreo cerrado. | 9 |
| Fase 4 | Después del viernes | ⏸ | Reporte, diagrama, video editado y ensayo de la presentación (con plan B local). | 10 |

Hitos (fechas límite internas):

| Hito | Fecha límite | Responsable | Qué tiene que existir |
| --- | --- | --- | --- |
| H0 | Hoy, antes de la clase | Producción | Repo `gasolina-mlops` en GitHub con la estructura, la API mínima y la imagen en GHCR. Esquemas y volúmenes creados en Databricks. |
| H1 | Miércoles 11, 10:00 p. m. | Modelos y Datos | Modelos: OCR + reglas funcionando en la Mac con `gasolina-evaluar` (merge a `main`). Datos: bronce y plata de MEM y FRED, y `features_forecast` en oro. |
| H2 | Jueves 12, 2:00 p. m. | Todos | Modelos: experimentos en MLflow, pronóstico y artifacts en `g6_oro/artifacts`. Datos: plata y oro con fotos reales, `reglas.json`, `historico.json`, job semanal. Producción: API completa, página, CI y logs simulados subidos a bronce. |
| H3 | Jueves 12, 10:00 p. m. | Todos (coordina Producción) | Simulacro completo en la Mac con artifacts reales (sección 8.6). Datos: `06_monitoreo` y dashboard funcionando con los logs simulados. A partir de aquí, `main` se congela: solo arreglos. |
| H4 | Viernes 13, en clase | Producción (los demás apoyan) | Despliegue final y evidencias (sección 9). |

---

## 3. Roles y reparto

Somos 3 personas. Cada una tiene un instructivo propio en `instructivos_equipo/`:

| Rol | Quién | Instructivo | Secciones del viejo que absorbe |
| --- | --- | --- | --- |
| Producción (y coordinación) | Ariela | `1_PRODUCCION_Ariela.md` | 3.1–3.3, 5, 11, 12, 13.2 (cron), 14, 16 |
| Datos | Compañero 1: ________ | `2_DATOS.md` | 7, 8, 13 (jobs, monitoreo, dashboard) |
| Modelos | Compañero 2: ________ | `3_MODELOS.md` | 3.4, 6, 9, 10 |
| Todos | — | Sección 10 de este documento | 15 (reporte), presentación |

Por qué Producción es de Ariela: solo su llave SSH entra al servidor y ella tiene el token de Databricks. Por eso ella también corre todo durante las ventanas ▶.

### 3.1 Dueños de archivos (para no pisarse en Git)

| Rol | Archivos y carpetas que le pertenecen |
| --- | --- |
| Producción | `pyproject.toml`, `config/`, `src/gasolina/api/`, `src/gasolina/sync.py`, `src/gasolina/config.py`, funciones `sync` y `api` de `cli.py`, `docker/`, `docker-compose.yml`, `scripts/`, `.github/`, `artifacts_demo/`, `tests/test_api.py`, `tests/test_contratos.py`, `docs/`, `README.md` |
| Modelos | `metadata.py`, `ocr.py`, `reglas.py`, `extraccion.py`, `forecast.py`, funciones `extraer` y `evaluar` de `cli.py`, sus tests, `notebooks/04_experimentos_ocr.py`, `notebooks/05_forecast.py` |
| Datos | `externos.py`, `features.py`, sus tests, `notebooks/00_setup.sql`, `01_bronce_ingesta.py`, `02_plata.py`, `03_oro.py`, `06_monitoreo.py`, `notebooks/README.md` |

Si alguien necesita cambiar un archivo que no es suyo (por ejemplo, agregar una dependencia en `pyproject.toml` o un valor en `config.yaml`), lo pide en el chat del equipo y lo hace la dueña o el dueño.

### 3.2 Flujo de Git

- Ramas: `produccion`, `datos` y `modelos`. Nadie trabaja directo en `main`.
- Para integrar: Pull Request a `main`. El CI tiene que pasar (verde) antes del merge.
- Antes de empezar cada sesión de trabajo: `git checkout main && git pull && git checkout <tu-rama> && git merge main`.
- En Databricks, cada persona tiene su propio Git folder (sección 8.2.3) y hace Pull después de cada merge.
- Fotos, PDFs, CSV y tokens nunca van al repo (ya están en `.gitignore`).

---

## 4. Contratos entre roles (lo que permite trabajar en paralelo)

Estas estructuras son obligatorias. Gracias a ellas, Producción puede terminar la API con datos de ejemplo mientras Modelos y Datos construyen los reales. Si alguien necesita cambiar un contrato, lo avisa en el chat y se actualiza este documento antes de tocar código.

### 4.1 Salida de `extraer_precios` (Modelos la produce; la API y `02_plata` la consumen)

```json
{
  "archivo": "IMG_8271.jpg",
  "modo": "real",
  "metadata": {
    "archivo": "IMG_8271.jpg",
    "fecha_hora": "2026-07-09T08:12:33",
    "lat": 14.5600,
    "lon": -90.4628,
    "altitud": 1502.3,
    "modelo_camara": "iPhone 14",
    "ancho": 4032,
    "alto": 3024,
    "sha256": "…"
  },
  "ruta_a": {"total": 150.00, "galones": 3.938, "precio_a": 38.09},
  "precios": {"diesel": 35.59, "regular": 37.09, "super": 38.09, "vpower": 38.59},
  "fuentes": {"diesel": "ruta_B", "regular": "ruta_B", "super": "ambas", "vpower": "ruta_B"},
  "combustible_despachado": "super",
  "validaciones": [
    {"nombre": "formato_y_rango", "estado": "ok", "mensaje": "4 precios en rango"}
  ],
  "score_confianza": 0.93,
  "estrategia": "fusion",
  "motor": "rapidocr",
  "preproc": "gris_clahe",
  "segunda_pasada": false,
  "tiempo_ms": 850,
  "version_modelo": "0.1.0",
  "detecciones_crudas": []
}
```

- `modo`: `"stub"` mientras no exista el OCR real (precios en `null`), `"real"` después.
- `fuentes`: `ruta_A`, `ruta_B`, `ambas`, `corregido_por_ruta_A` o `inferido`.
- `validaciones[].estado`: `ok`, `falla` o `advertencia`.
- Cualquier valor que no se pueda leer va como `null`; ninguna clave se omite.

### 4.2 Artifacts en `/Volumes/workspace/g6_oro/artifacts/` (Datos y Modelos los producen; la API los consume)

Todos los JSON llevan `"origen": "databricks"` (los de `artifacts_demo/` llevan `"origen": "demo"`) y `"fecha"` en ISO.

| Archivo | Lo produce | Notebook | Estructura |
| --- | --- | --- | --- |
| `ocr_config.json` | Modelos | `04_experimentos_ocr` | `{"origen", "fecha", "version", "motor", "preproc", "segunda_pasada", "estrategia", "umbral_score", "metricas": {"accuracy_precio", "mae", "pct_fotos_4_correctos", "tiempo_ms_promedio"}, "mlflow_run_id"}` |
| `forecast.joblib` | Modelos | `05_forecast` | Modelo champion (la API no lo necesita para responder; queda como respaldo y evidencia). |
| `forecast_meta.json` | Modelos | `05_forecast` | `{"origen", "fecha", "modelo", "version", "features": [...], "metricas_validacion": {"mae", "rmse", "mape", "mejora_vs_baseline_pct"}, "fecha_entrenamiento"}` |
| `predicciones.json` | Modelos | `05_forecast` | `{"origen", "fecha", "semana_objetivo": "2026-W47", "modelo", "version", "predicciones": [{"combustible", "prediccion", "intervalo_inf", "intervalo_sup"}]}` |
| `reglas.json` | Datos | `03_oro` | `{"origen", "fecha", "rango_precio": {"diesel": [min, max], "regular": [...], "super": [...], "vpower": [...]}, "referencia_mem": {"fecha_referencia", "diesel", "regular", "super"}, "diferencias": {"super_menos_regular": 1.00, "vpower_menos_super": 0.50, "tolerancia": 0.05}}` |
| `historico.json` | Datos | `03_oro` | `{"origen", "fecha", "mem": [{"semana", "fecha", "combustible", "precio"}], "fotos": [{"fecha", "combustible", "precio", "estacion_id", "score_confianza"}]}` |
| `monitoreo.json` | Datos | `06_monitoreo` | `{"origen", "fecha", "version_champion", "fecha_reentrenamiento", "error_produccion": {"mae"}, "error_validacion": {"mae"}, "drift_vs_mem_pct": {"diesel", "regular", "super"}, "alertas": [{"nombre", "activa", "valor", "umbral", "mensaje"}]}` |

### 4.3 Logs de producción (Producción los produce; `06_monitoreo` los consume)

Un archivo por día, `logs/predicciones_YYYYMMDD.jsonl`, una línea por llamada a `/extraer`:

```json
{"id": "uuid4", "timestamp": "2026-11-13T14:05:12-06:00", "sha256": "…", "archivo": "IMG_8271.jpg",
 "fecha_foto": "2026-07-09T08:12:33", "lat": 14.56, "lon": -90.4628,
 "precios": {"diesel": 35.59, "regular": 37.09, "super": 38.09, "vpower": 38.59},
 "fuentes": {"diesel": "ruta_B", "regular": "ruta_B", "super": "ambas", "vpower": "ruta_B"},
 "precio_a": 38.09, "combustible_despachado": "super", "coincide_a_b": true,
 "score_confianza": 0.93, "validaciones_fallidas": [], "latencia_ms": 912,
 "modo": "real", "version_modelo": "0.1.0", "origen_artifacts": "databricks", "entorno": "servidor"}
```

`entorno` es `"local"` para los logs simulados en la Mac y `"servidor"` para los del droplet, así el monitoreo puede separarlos.

### 4.4 Nombres en Databricks (todos los usan igual)

| Capa | Objetos |
| --- | --- |
| Bronce | Volumen `workspace.g6_bronce.crudos` con `fotos/`, `mem/`, `fred/`, `etiquetas/`, `api_logs/`; tabla `g6_bronce.inventario` |
| Plata | `g6_plata.lecturas_ocr`, `g6_plata.precios_mem`, `g6_plata.subsidios`, `g6_plata.exogenas_diarias`, `g6_plata.api_predicciones` |
| Oro | `g6_oro.precios_estacion`, `g6_oro.comparacion_mem`, `g6_oro.features_forecast`, `g6_oro.predicciones`, `g6_oro.monitoreo_diario`; volumen `g6_oro.artifacts`; modelos `g6_oro.extractor_gasolina` y `g6_oro.forecast_gasolina` (alias `champion`) |
| MLflow | Experimentos `/Users/<correo de Modelos>/g6_ocr_gasolina` y `/Users/<correo de Modelos>/g6_forecast_gasolina` |
| Jobs | `g6_pipeline_semanal` y `g6_monitoreo_diario` |

El catálogo es `workspace` salvo que en la sección 6.1 hayan anotado otro. Catálogo real: `________` (si es distinto, se cambia solo en `config/config.yaml` y en los widgets).

---

## 5. Conceptos mínimos (léelo una vez)

- Bronce, plata y oro: la misma idea de la Actividad 7. Bronce es una copia fiel de lo que llega (fotos, PDF, CSV). Plata son las tablas limpias. Oro es lo que consume alguien: históricos, predicciones, métricas y el modelo.
- Unity Catalog: el "archivero" de Databricks. Se organiza como `catálogo.esquema.tabla`. Los archivos (fotos, PDF) van en volúmenes: `/Volumes/catálogo/esquema/volumen/...`.
- Tabla Delta: una tabla de Databricks guardada en formato Delta, que permite historial y versiones (time travel). Se crea con `df.write.saveAsTable(...)`.
- Job: un notebook (o varios) que Databricks corre solo, con horario.
- MLflow: la bitácora de experimentos. Cada corrida guarda parámetros, métricas y archivos. El mejor modelo se registra con nombre y versión.
- API: un programa en el servidor que escucha peticiones. Le mandas una foto y te devuelve un JSON.
- Docker: una "caja" con el programa y todas sus dependencias, para que corra igual en cualquier lugar.
- GHCR (GitHub Container Registry): el lugar de GitHub donde queda guardada la imagen de Docker que construye GitHub Actions. El servidor la descarga con `docker compose pull`.
- Artifacts demo: archivos falsos pero con la estructura correcta, para que la API funcione antes de que existan los modelos reales. `/health` siempre dice si la API está usando artifacts demo o reales.

---

## 6. Fase 0 — Hoy, antes de la clase ⏸

Orden recomendado para Ariela (los compañeros hacen en paralelo lo de 6.6). Si el tiempo no alcanza, lo indispensable para la clase es: 6.2, 6.3 y 6.4. Si 6.4 no queda, igual se aprovecha la clase con el plan B de la sección 7.3.

### 6.1 ⭐ Databricks 🧱 (ya hecho)

Esto ya lo hiciste; queda aquí para tener todo en un solo lugar.

1. Busca en tu correo (también en spam) una invitación de Databricks enviada por el profesor. El asunto suele ser algo como "You've been added to a Databricks workspace".
2. Abre el enlace. Te lleva a una URL tipo `https://dbc-xxxx.cloud.databricks.com` o `https://xxxx.databricks.com`. Guarda esa URL, porque es tu workspace.
3. Inicia sesión con tu correo de la U (o con el que te invitó).
4. Si no encuentras invitación, escríbele al profesor: "Profe, ¿nos podría compartir el enlace del workspace de Databricks o invitarme con este correo?".

Cuando entres, revisa qué tienes:

1. En la barra izquierda, haz clic en Catalog. Anota qué catálogos ves (por ejemplo `workspace`, `main` o uno del curso).
2. Haz clic en New → Notebook. En la primera celda escribe y corre (Shift + Enter):

```sql
%sql
SHOW CATALOGS;
```

3. Luego prueba si puedes crear un esquema (cambia `workspace` por el catálogo que sí tengas):

```sql
%sql
CREATE SCHEMA IF NOT EXISTS workspace.g6_bronce;
```

- Si funciona, tienes permisos. Déjalo, porque lo vamos a usar.
- Si sale `PERMISSION_DENIED`, pregúntale al profesor en qué catálogo pueden crear esquemas.

4. Revisa si hay S3: en Catalog → engranaje (⚙) → External Locations. Si ves alguna relacionada con el curso o el equipo, anota su nombre y URL (`s3://...`). Si no hay ninguna, no pasa nada: usamos volúmenes administrados (sección 8.2.1).
5. Crea un token para que el servidor pueda hablar con Databricks: tu foto de perfil (arriba a la derecha) → Settings → Developer → Access tokens → Generate new token. Ponle de nombre `servidor-g6` y 90 días de vigencia. Copia el token (empieza con `dapi...`) y guárdalo en un lugar seguro, como el gestor de contraseñas o una nota privada. Nunca lo subas a GitHub ni lo pegues en un documento compartido. Si la opción no aparece, el workspace no permite tokens; hay un plan B en la sección 7.4.

Checklist:

- [x] Puedo entrar al workspace y tengo su URL anotada.
- [x] Sé en qué catálogo puedo crear esquemas: `________`.
- [x] Sé si hay external location de S3: no.
- [x] Tengo un token `dapi...` guardado.

Para que los compañeros trabajen: cada uno entra con su propia invitación. Si alguno no tiene acceso, que le escriba hoy al profesor.

### 6.2 ⭐ Alias SSH en tu Mac 💻 (no necesita el servidor encendido)

```bash
nano ~/.ssh/config
```

Ve al final del archivo (con las flechas) y pega:

```
Host gasolina
    HostName 159.65.111.14
    User cc3105
    IdentityFile ~/.ssh/id_ed25519
    ServerAliveInterval 30
```

Guarda con `Ctrl + O`, Enter, y sal con `Ctrl + X`. En clase te conectarás con `ssh gasolina`.

### 6.3 ⭐ GitHub 🐙

1. Crea un repositorio nuevo llamado `gasolina-mlops`, público. Público ahorra tiempo de servidor: se clona sin llaves y la imagen de Docker se descarga sin iniciar sesión. Por eso nunca se suben tokens ni datos.
2. Agrega como colaboradores a tus compañeros: Settings → Collaborators.
3. Settings → Actions → General → Workflow permissions → "Read and write permissions" → Save (para que el CI pueda publicar la imagen).
4. No subas fotos ni datos pesados al repo. Esos van a Databricks (bronce).

### 6.4 ⭐ Repo base con la API mínima 💻 (lo más importante de hoy)

Primero, copia este instructivo y la carpeta `instructivos_equipo/` dentro de `Proyecto/` (ya están ahí si estás leyendo esto desde tu Mac). Luego abre Claude Code en la carpeta `Proyecto` y pega:

```
PROMPT PARA CLAUDE CODE
Estoy en la carpeta Proyecto de mi curso de ML Engineering. Crea el repositorio base
gasolina-mlops (subcarpeta gasolina-mlops/). Contexto clave: el servidor de producción
(DigitalOcean) solo está encendido durante la clase (1.5 h). Hoy en clase quiero desplegar
ESTE repo base, así que todo lo de producción tiene que funcionar ya, con artifacts de
ejemplo, aunque los modelos todavía no existan. Antes de empezar lee
../INSTRUCTIVO_GENERAL.md, sección 4 (contratos): esas estructuras son obligatorias.

Estructura:

gasolina-mlops/
  pyproject.toml          # paquete "gasolina", Python >=3.10, setuptools, layout src/
  README.md
  .gitignore              # ignora datos/, *.jpg, *.HEIC, .env, artifacts/, logs/, __pycache__, .venv*, mlruns
  .env.example            # DATABRICKS_HOST=, DATABRICKS_TOKEN=, GOLD_ARTIFACTS_PATH=,
                          # BRONZE_LOGS_PATH=, ARTIFACTS_DIR=, IMAGEN_DOCKER=
  config/config.yaml      # catálogo (workspace), rutas de capas, nombres de tablas,
                          # rangos válidos de precio (20-60), reglas (super-regular=1.00,
                          # vpower-super=0.50, tolerancia 0.05), umbral_score 0.7,
                          # tipo_cambio 7.7, umbrales de alertas de monitoreo
  artifacts_demo/         # artifacts FALSOS pero válidos según el contrato 4.2:
                          # ocr_config.json, reglas.json, forecast_meta.json,
                          # predicciones.json, historico.json, monitoreo.json.
                          # Todos con "origen": "demo".
  src/gasolina/
    __init__.py           # __version__ = "0.1.0"
    config.py             # carga config.yaml y variables de entorno
    metadata.py           # STUB documentado: leer_metadata(ruta) -> dict del contrato 4.1
                          # (por ahora solo archivo y sha256 reales, el resto None)
    ocr.py                # STUB documentado (lo implementa la persona de Modelos)
    reglas.py             # STUB documentado (Modelos)
    extraccion.py         # STUB: extraer_precios(ruta, motor="rapidocr", preproc="gris_clahe",
                          # estrategia="fusion", referencia=None) devuelve un dict con TODAS
                          # las claves del contrato 4.1, precios en None y "modo": "stub"
    externos.py           # STUB documentado (lo implementa la persona de Datos)
    features.py           # STUB documentado (Datos)
    forecast.py           # STUB documentado (Modelos)
    sync.py               # COMPLETO (ver abajo)
    cli.py                # entrypoints; extraer y evaluar como stubs que imprimen JSON
    api/
      app.py              # COMPLETO en versión mínima (ver abajo)
      static/index.html   # página sencilla en español: subir foto -> llama /extraer y
                          # muestra el JSON; muestra /health. (La versión final llega después.)
  notebooks/README.md     # orden de ejecución: 00_setup, 01_bronce_ingesta, 02_plata, 03_oro,
                          # 04_experimentos_ocr, 05_forecast, 06_monitoreo
  notebooks/00_setup.sql  # CREATE SCHEMA/VOLUME de la sección 8.2.1 del instructivo
  tests/test_api.py, tests/test_contratos.py
  docker/Dockerfile
  docker-compose.yml
  scripts/servidor_check.sh
  scripts/deploy.sh
  scripts/fin_de_clase.sh
  scripts/generar_trafico.py
  .github/workflows/ci.yml
  .github/workflows/deploy.yml
  docs/                   # copia aquí ../INSTRUCTIVO_GENERAL.md y ../instructivos_equipo/*.md

Dependencias base: pillow, pillow-heif, numpy, pandas, pyyaml, rapidocr_onnxruntime==1.3.24,
opencv-python-headless, pdfplumber, scikit-learn, joblib, requests.
Extras: [api] fastapi, uvicorn[standard], python-multipart, databricks-sdk;
[easyocr] easyocr; [dev] pytest, ruff, httpx.

Entrypoints en [project.scripts]:
  gasolina-extraer = gasolina.cli:extraer   (ruta de imagen o carpeta, imprime JSON)
  gasolina-evaluar = gasolina.cli:evaluar   (compara contra datos/etiquetas.csv)
  gasolina-sync    = gasolina.cli:sync      (subcomandos descargar | subir-logs)
  gasolina-api     = gasolina.cli:api       (uvicorn en 0.0.0.0:8000)

sync.py (completo):
- "descargar": con databricks-sdk (WorkspaceClient lee DATABRICKS_HOST y DATABRICKS_TOKEN),
  lista y descarga todos los archivos de GOLD_ARTIFACTS_PATH a ARTIFACTS_DIR (default
  ./artifacts) y guarda manifest.json con fecha y lista de archivos.
- "subir-logs": sube los logs/*.jsonl que no se hayan subido antes a BRONZE_LOGS_PATH,
  llevando el registro en logs/.subidos.json (así funciona igual dentro de Docker,
  porque logs/ es un volumen). Un archivo del día actual se vuelve a subir si cambió de tamaño.
- Usa w.files.download / w.files.upload. Mensajes claros si el token es inválido (401/403)
  o si no hay red.

app.py (mínimo pero real):
- Carga artifacts de ARTIFACTS_DIR; si la carpeta está vacía o no existe, usa artifacts_demo/
  y lo reporta. Los JSON se vuelven a leer cuando cambia su fecha de modificación (así un
  "gasolina-sync descargar" los actualiza sin reiniciar la API).
- GET /health: status, version del paquete, origen de artifacts (demo|databricks),
  versión y fecha de cada artifact, modo de extracción (stub|real), hora del servidor.
- POST /extraer (multipart, campo "foto", JPG/PNG/HEIC, máx. 15 MB): llama a extraer_precios
  con ocr_config.json; ?debug=true incluye detecciones_crudas. 400 si no es imagen.
- GET /pronostico: devuelve predicciones.json. GET /historico: historico.json + las
  predicciones. GET /metricas: contadores en memoria (total, % score >= umbral, p50/p95).
- GET /monitoreo/produccion y GET /monitoreo/modelo: versiones mínimas que respondan con
  "disponible": false si faltan datos.
- Cada /extraer escribe una línea en logs/predicciones_YYYYMMDD.jsonl con el contrato 4.3.
- Sirve static/index.html en "/".

docker/Dockerfile: python:3.11-slim, apt install libgl1 libglib2.0-0, instala el paquete con
[api] SIN easyocr, copia artifacts_demo, usuario no root, EXPOSE 8000, HEALTHCHECK a /health
(con python, sin curl), CMD gasolina-api.
docker-compose.yml: servicio "api" con image: ${IMAGEN_DOCKER:-gasolina-mlops:local} y
build (context ., dockerfile docker/Dockerfile), puertos 8000:8000, volúmenes
./artifacts:/app/artifacts y ./logs:/app/logs, env_file .env, environment
ARTIFACTS_DIR=/app/artifacts, restart: unless-stopped (así la API se levanta sola cada vez
que el profesor encienda el servidor).

scripts/servidor_check.sh: corre whoami, hostname, /etc/os-release, nproc, free -h, df -h /,
which git python3 docker tmux, python3 --version, docker ps, docker compose version, groups,
sudo -n true, ss -tlnp; imprime un resumen con "DOCKER: SÍ/NO", "RAM: X", "PUERTO 8000 LIBRE:
SÍ/NO" y guarda todo en ~/servidor_check.txt.

scripts/deploy.sh (correr EN EL SERVIDOR, comentarios en español en cada paso):
- Flags: --sin-pull (no hace git pull), --modo docker|venv (por defecto detecta: si
  "docker ps" funciona usa docker, si no usa venv).
- Pasos: git pull (salvo --sin-pull); crea logs/ y artifacts/; sincroniza artifacts
  (modo docker: docker compose run --rm --no-deps api gasolina-sync descargar; modo venv:
  .venv/bin/gasolina-sync descargar); si la sincronización falla, avisa y sigue con lo que
  haya (la API cae a artifacts_demo).
- Modo docker: si IMAGEN_DOCKER está definida intenta docker compose pull; si falla, hace
  docker compose up -d --build; si no, up -d directo.
- Modo venv: crea .venv si no existe, pip install -e ".[api]", detiene la instancia anterior
  (archivo api.pid), arranca con nohup gasolina-api > logs/api.log 2>&1 & y guarda el PID;
  además instala (si no existe) una línea @reboot en crontab que corre deploy.sh --sin-pull.
- Espera hasta 90 s a que /health responda y muestra el JSON. Si falla, muestra las últimas
  40 líneas del log y sale con código 1.

scripts/fin_de_clase.sh: corre subir-logs (según el modo), muestra estado de la API, cuántas
peticiones hubo hoy y recuerda que la API se levanta sola al encender el servidor.

scripts/generar_trafico.py: --url (default http://localhost:8000), --carpeta (default ../datos),
--repeticiones N; manda cada foto a /extraer, imprime una tabla con precios, score y latencia.
Sirve para simular tráfico de producción y para la prueba de humo del viernes.

.github/workflows/ci.yml: en push y PR a main: Python 3.11, pip install -e ".[api,dev]",
ruff check, pytest. Solo en push a main y si lo anterior pasa: construir la imagen para
linux/amd64 y publicarla en ghcr.io/<owner en minúsculas>/gasolina-mlops con tags latest y
el sha (permissions: packages: write; usa GITHUB_TOKEN).
.github/workflows/deploy.yml: SOLO workflow_dispatch (manual, porque el servidor casi siempre
está apagado). Se conecta por SSH con los secrets SSH_HOST, SSH_USER y SSH_PRIVATE_KEY y corre
"cd ~/apps/gasolina-mlops && bash scripts/deploy.sh".

Tests: test_api.py (health responde 200 con artifacts demo; /extraer con ../datos/IMG_8271.jpg
si existe, si no skip; /pronostico responde) y test_contratos.py (los JSON de artifacts_demo
tienen exactamente las claves del contrato 4.2).

Al terminar: corre pytest, levanta gasolina-api, prueba con curl /health y
/extraer con ../datos/IMG_8271.jpg, apágala y, si tengo Docker en la Mac, corre
docker compose build. Muéstrame un resumen corto de qué quedó y qué falló.
```

Luego, en la Terminal 💻:

```bash
cd "/Users/arielamishaancohen/Documents/UVG/Clases/Semestre 10 (2026)/ML Engineering/Proyecto/gasolina-mlops"
git init
git add .
git commit -m "Repo base: estructura, API mínima, Docker, scripts y CI"
git branch -M main
git remote add origin https://github.com/TU_USUARIO/gasolina-mlops.git
git push -u origin main
git checkout -b produccion && git push -u origin produccion
git checkout -b datos && git push -u origin datos
git checkout -b modelos && git push -u origin modelos
git checkout produccion
```

Antes del `git add .`, confirma con `git status` que no aparecen `.env`, fotos ni la carpeta `artifacts/`.

(Cambia `TU_USUARIO` por tu usuario de GitHub.)

Ambiente local 💻:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[api,dev]"
```

Si tienes `uv`, puedes usar `uv venv && source .venv/bin/activate && uv pip install -e ".[api,dev]"`, que es más rápido.

Después del push:

1. 🐙 Ve a la pestaña Actions del repo y espera a que el workflow `ci` termine en verde (incluye construir y publicar la imagen; tarda unos 5 a 8 minutos).
2. 🐙 Ve a tu perfil → Packages → `gasolina-mlops` → Package settings → Change visibility → Public. Sin esto, el servidor no puede descargar la imagen.
3. 💻 Prueba que la imagen se descarga:

```bash
docker pull ghcr.io/TU_USUARIO_EN_MINUSCULAS/gasolina-mlops:latest
```

(Si no tienes Docker en la Mac, sáltate esto; en clase el servidor lo prueba.)

4. 🧱 Crea los esquemas y volúmenes (2 minutos; si la persona de Datos ya lo hizo, sáltalo). En un notebook:

```sql
%sql
CREATE SCHEMA IF NOT EXISTS workspace.g6_bronce;
CREATE SCHEMA IF NOT EXISTS workspace.g6_plata;
CREATE SCHEMA IF NOT EXISTS workspace.g6_oro;
CREATE VOLUME IF NOT EXISTS workspace.g6_bronce.crudos;
CREATE VOLUME IF NOT EXISTS workspace.g6_oro.artifacts;
```

5. 🧱 Sube los 6 JSON de `artifacts_demo/` a `/Volumes/workspace/g6_oro/artifacts/` (Catalog → `g6_oro` → Volumes → `artifacts` → Upload to this volume). Así en clase pruebas el sync de verdad. Más adelante, Datos y Modelos los reemplazan con los reales.
6. 🧱 En `/Volumes/workspace/g6_bronce/crudos/` crea el directorio `api_logs` (Create directory).

Checklist:

- [ ] El repo está en GitHub con la estructura y el CI está en verde.
- [ ] La imagen está publicada y es pública en GHCR.
- [ ] `gasolina-api` corre en la Mac y `curl localhost:8000/health` responde.
- [ ] Los artifacts demo están en `g6_oro/artifacts` y existe `crudos/api_logs`.

### 6.5 ⭐ Preparar lo que vas a pegar en el servidor 💻

En clase no hay tiempo de buscar cosas. Deja listo, en una nota privada (no en el repo ni en un documento compartido):

1. El contenido del `.env`:

```
DATABRICKS_HOST=https://URL-DE-TU-WORKSPACE
DATABRICKS_TOKEN=dapi...
GOLD_ARTIFACTS_PATH=/Volumes/workspace/g6_oro/artifacts
BRONZE_LOGS_PATH=/Volumes/workspace/g6_bronce/crudos/api_logs
ARTIFACTS_DIR=/app/artifacts
IMAGEN_DOCKER=ghcr.io/TU_USUARIO_EN_MINUSCULAS/gasolina-mlops:latest
```

Prueba ese mismo `.env` en tu Mac: cópialo a `gasolina-mlops/.env` y corre `set -a; source .env; set +a; ARTIFACTS_DIR=./artifacts gasolina-sync descargar`. Si descarga los 6 JSON demo, el token y las rutas están bien. Si da 401/403, genera otro token (sección 6.1, paso 5). Recomendación: como el token viejo quedó escrito en el instructivo anterior, genera uno nuevo ahora y revoca el anterior.

2. La llave para el deploy automático (GitHub Actions). Una llave nueva, solo para GitHub (no uses la tuya):

```bash
ssh-keygen -t ed25519 -f ~/.ssh/gha_deploy -C "github-actions-g6" -N ""
cat ~/.ssh/gha_deploy.pub
```

Guarda la línea que imprime (la `.pub`); en clase se agrega al servidor. La privada va desde ya en GitHub 🐙 → Settings → Secrets and variables → Actions → New repository secret:

| Secret | Valor |
| --- | --- |
| `SSH_HOST` | `159.65.111.14` |
| `SSH_USER` | `cc3105` |
| `SSH_PRIVATE_KEY` | Todo el contenido de `cat ~/.ssh/gha_deploy` (sin `.pub`), incluidas las líneas BEGIN y END |

3. El mensaje para el profesor (sección 12), para preguntárselo en persona al inicio de la clase.

### 6.6 Lo que hacen los compañeros hoy (sin necesitar el repo)

Mientras Ariela arma el repo, mándales su instructivo por WhatsApp. Lo que pueden hacer de inmediato:

Persona de Modelos: etiquetas manuales (la "verdad" para medir el OCR). Sin esto no se puede decir qué tan bueno es el modelo. Abre cada foto en Vista Previa, haz zoom en las 4 pantallitas y llena este archivo. Guárdalo como `Proyecto/datos/etiquetas.csv`:

```csv
archivo,diesel,regular,super,vpower,venta_total,galones
IMG_8271.jpg,35.59,37.09,38.09,38.59,150.00,3.938
IMG_8286.jpg,,,,,,
IMG_8304.jpg,,,,,,
IMG_8322.jpg,,41.09,42.09,42.59,150.00,
IMG_8325.jpg,,,,,,
```

Ya está lo que se alcanza a leer en dos fotos. Hay que verificarlo con zoom y completar lo que falta. Si un número no se lee bien ni a simple vista, se deja vacío y se anota en el reporte como limitación.

✨ Recomendado (todos): tomar más fotos esta semana (cada integrante 3 a 5 fotos en distintas gasolineras Shell, con la ubicación del iPhone activada, que se vea la pantalla de "Esta Venta" y las 4 pantallitas). Con 20 a 30 fotos la evaluación del OCR es mucho más creíble. Se agregan a `etiquetas.csv` y se mandan a Ariela o directo a bronce.

Persona de Datos: descargar los PDF del MEM y los CSV de FRED (sección 8.2.4) y buscar las fechas del subsidio. No necesita el repo para eso.

Ariela les pasa las 5 fotos originales (están en `Proyecto/datos/`) por Drive o WhatsApp como documento (no como foto, para no perder la metadata EXIF).

### 6.7 Checklist "lista para la clase de hoy"

- [ ] `~/.ssh/config` tiene el alias `gasolina`.
- [ ] Repo en GitHub, público, CI en verde, imagen pública en GHCR.
- [ ] `.env` probado en la Mac (descarga artifacts demo).
- [ ] Secrets de GitHub creados; tengo a mano la línea de `gha_deploy.pub`.
- [ ] Preguntas para el profesor listas (sección 12).
- [ ] Laptop cargada, Terminal con dos pestañas: una para el servidor y otra para la Mac.

---

## 7. Fase 1 — Hoy en la clase ▶ (1:30 h)

Meta: probar toda la infraestructura con la API mínima. Si esto queda hoy, el viernes solo se actualiza el código.

### 7.1 Guion minuto a minuto

| Minuto | Dónde | Qué hacer | Cómo sabes que quedó |
| --- | --- | --- | --- |
| 0–5 | 🧑‍🏫 | Pregúntale al profesor lo de la sección 12 (sobre todo: ¿enciende el servidor el viernes y el día de la presentación? ¿Docker y puerto 8000?). | Respuestas anotadas. |
| 5–10 | 🌊 | `ssh gasolina`, luego clonar (7.2). | Ves la carpeta `~/apps/gasolina-mlops`. |
| 10–15 | 🌊 | `bash scripts/servidor_check.sh` | Sabes si hay Docker, RAM y puerto 8000 libre. |
| 15–20 | 🌊 | Crear el `.env` (7.2). | `cat .env` muestra 6 líneas (no lo muestres en pantalla compartida). |
| 20–35 | 🌊 | `bash scripts/deploy.sh` | Termina con el JSON de `/health` y `"status": "ok"`. |
| 35–45 | 💻 | Probar desde la Mac (7.2). | `curl http://159.65.111.14:8000/health` responde y la página abre en el navegador. |
| 45–55 | 🌊 | Agregar la llave de GitHub Actions (7.2) y correr el workflow `deploy` manual. | El workflow `deploy` sale en verde. |
| 55–65 | 🌊 | Probar el ciclo de logs: subir 2 fotos desde la Mac y correr `bash scripts/fin_de_clase.sh`. | En Databricks aparece el `.jsonl` en `crudos/api_logs/`. |
| 65–75 | 🌊 | Cron de subida de logs (7.2). Probar que la API se levanta sola: `docker compose restart` (o pedirle al profesor un reinicio si se puede). | `crontab -l` muestra la línea; `/health` vuelve a responder. |
| 75–85 | 💻 | Evidencias: capturas de `servidor_check`, `/health`, la página, `docker compose ps`, el workflow verde. Copiar `~/servidor_check.txt` a la Mac. | Capturas en `Proyecto/evidencias/clase_martes/`. |
| 85–90 | 🌊 | `bash scripts/fin_de_clase.sh` y anotar qué falló para arreglarlo antes del viernes. | Lista de pendientes en el chat. |

### 7.2 Comandos del guion

Clonar y revisar el servidor 🌊:

```bash
ssh gasolina
mkdir -p ~/apps && cd ~/apps
git clone https://github.com/TU_USUARIO/gasolina-mlops.git
cd gasolina-mlops
bash scripts/servidor_check.sh
```

Cómo interpretar `servidor_check`:

| Resultado | Significa | Qué hacer |
| --- | --- | --- |
| `docker ps` muestra una tabla (aunque vacía) | Puedes usar Docker. | Ruta normal: `deploy.sh` detecta Docker solo. |
| `docker ps` dice `permission denied` | Docker existe pero tu usuario no está en el grupo `docker`. | Pídele al profesor en ese momento: "¿Puede agregar al usuario cc3105 al grupo docker?" (después hay que salir y volver a entrar por SSH). Mientras tanto, `deploy.sh` usa la ruta venv sola. |
| `free -h` muestra menos de 1.5 GB de RAM | Servidor chico. | RapidOCR sí cabe. No uses EasyOCR en producción. |
| `SIN SUDO` | No puedes instalar paquetes del sistema. | Normal. Todo se hace en tu carpeta de usuario. |
| Puerto 8000 ocupado | Otro equipo lo usa. | Cambia `8000:8000` por `8010:8000` en `docker-compose.yml` (en el repo, con commit) y usa ese puerto en todo. |

Si el repo fuera privado (no recomendado), en el servidor crea una llave solo para GitHub con `ssh-keygen -t ed25519 -f ~/.ssh/github_deploy -C "deploy-g6"` y luego `cat ~/.ssh/github_deploy.pub`. En GitHub ve a Repo → Settings → Deploy keys → Add (solo lectura) y pégala. Luego clona con:

```bash
GIT_SSH_COMMAND="ssh -i ~/.ssh/github_deploy" git clone git@github.com:TU_USUARIO/gasolina-mlops.git
```

Secretos (`.env`) 🌊:

```bash
cd ~/apps/gasolina-mlops
nano .env        # pega el contenido de tu nota privada (6.5)
chmod 600 .env
```

Nunca hagas `git add .env` (ya está en `.gitignore`). Ojo: el usuario `cc3105` probablemente es compartido. Todo lo que pongan en `~/apps` lo ven los demás. Para eso está bien, pero no dejen tokens personales en otros lados.

Desplegar 🌊:

```bash
bash scripts/deploy.sh
```

Qué hace `deploy.sh`: `git pull` → sincroniza artifacts desde Databricks (dentro del contenedor, así no hace falta instalar nada en el servidor) → descarga la imagen de GHCR (si falla, la construye ahí) → `docker compose up -d` → espera a que `/health` responda. Si no hay Docker, hace lo mismo con un venv y `nohup`, y agrega una línea `@reboot` al crontab para que la API se levante sola al encender el servidor.

Probar desde la Mac 💻:

```bash
curl http://159.65.111.14:8000/health
cd ".../Proyecto"
curl -F "foto=@datos/IMG_8271.jpg" http://159.65.111.14:8000/extraer
```

Y abre en el navegador `http://159.65.111.14:8000`. Ahí está la interfaz. Hoy los precios saldrán en `null` (modo stub): es lo esperado.

Si desde el servidor funciona pero desde tu Mac no, el puerto 8000 está bloqueado por el firewall. Pídele al profesor: "¿Podría abrir el puerto 8000 en el droplet del equipo?". Mientras tanto, usa un túnel SSH desde tu Mac: `ssh -L 8000:localhost:8000 gasolina` y luego abre `http://localhost:8000`.

Llave de GitHub Actions 🌊 (pregúntale antes al profesor, porque es su servidor):

```bash
echo "PEGA-AQUÍ-LA-LÍNEA-DE-gha_deploy.pub" >> ~/.ssh/authorized_keys
```

Luego 🐙 Actions → `deploy` → Run workflow. Si sale en verde, el CD funciona. Si el profesor prefiere agregarla él, mándale la `.pub`.

Cron de subida de logs 🌊 (cada hora mientras el servidor esté encendido):

```bash
crontab -e
# agrega esta línea (una sola línea):
0 * * * * cd ~/apps/gasolina-mlops && docker compose run --rm --no-deps api gasolina-sync subir-logs >> logs/sync.log 2>&1
```

(Si estás en modo venv: `0 * * * * cd ~/apps/gasolina-mlops && set -a && . ./.env && set +a && .venv/bin/gasolina-sync subir-logs >> logs/sync.log 2>&1`.)

Para salir del servidor: `exit`.

Checklist de la clase de hoy:

- [ ] `ssh gasolina` funciona.
- [ ] Sé si tengo Docker, cuánta RAM hay y si hay `git` y `python3`.
- [ ] `http://159.65.111.14:8000/health` responde (o vía túnel).
- [ ] `gasolina-sync descargar` funcionó desde el servidor (`/health` dice origen `databricks`).
- [ ] Un `.jsonl` llegó a `crudos/api_logs/`.
- [ ] El workflow `deploy` corrió en verde (o sé qué falta).
- [ ] Cron instalado y la API se levanta sola tras un reinicio.

### 7.3 Plan B de hoy: si el repo base no quedó listo

Igual se aprovecha la clase para resolver todas las incógnitas del servidor. Corre esto 🌊 y guarda la salida:

```bash
whoami; hostname
cat /etc/os-release | head -3
nproc; free -h; df -h /
which git python3 docker conda uv tmux
python3 --version
docker ps 2>&1 | head -3
docker compose version 2>&1 | head -1
groups
sudo -n true 2>&1 && echo "TENGO SUDO" || echo "SIN SUDO"
ss -tlnp 2>/dev/null | head
```

Prueba el puerto sin código 🌊 → 💻:

```bash
# en el servidor:
python3 -m http.server 8000
# en tu Mac (otra pestaña):
curl -I http://159.65.111.14:8000
# si responde "HTTP/1.0 200 OK", el puerto está abierto. Vuelve al servidor y apágalo con Ctrl + C.
```

Prueba Docker 🌊: `docker run --rm hello-world`.

Prueba la conexión del servidor con Databricks 🌊 (el token no queda en el historial):

```bash
read -s DATABRICKS_TOKEN; export DATABRICKS_TOKEN
curl -s -o /dev/null -w "%{http_code}\n" -H "Authorization: Bearer $DATABRICKS_TOKEN" \
  https://URL-DE-TU-WORKSPACE/api/2.1/unity-catalog/catalogs
# 200 = el servidor puede hablar con Databricks
```

Agrega la llave de GitHub Actions (7.2). Con eso, el viernes solo falta desplegar.

### 7.4 Plan B para los artifacts (si el token no funciona desde el servidor)

Descarga los artifacts en tu Mac con `gasolina-sync descargar` (o manualmente desde el Catalog Explorer, cada archivo tiene la opción Download) y cópialos al servidor 💻:

```bash
scp artifacts/* gasolina:~/apps/gasolina-mlops/artifacts/
```

Documenten en el reporte que en una empresa esto sería automático con un service principal.

---

## 8. Fase 2 — Martes noche a jueves noche ⏸ (desarrollo en paralelo)

Todo esto se hace sin servidor. El orden dentro de cada rol importa; entre roles, se trabaja en paralelo gracias a los contratos de la sección 4.

### 8.1 Modelos — OCR + reglas en la Mac 💻 (hito H1)

La idea es hacerlo funcionar local con las 5 fotos antes de llevarlo a Databricks. Es más rápido para iterar. Estructura de carpetas para que funcionen las rutas `../datos`:

```
<tu carpeta del proyecto>/
  datos/            # las 5 fotos + etiquetas.csv (+ mem/ para Datos)
  gasolina-mlops/   # el repo clonado
```

#### 8.1.1 ⭐ Metadata

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

#### 8.1.2 ⭐ OCR + reglas

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

Checklist:

- [ ] `gasolina-evaluar` da una tabla con métricas por motor, preprocesamiento y estrategia.
- [ ] Hay al menos una configuración con ≥ 90 % de precios correctos en las fotos etiquetadas (meta). Si no se llega, documenten por qué y cómo las reglas lo compensan.
- [ ] Tests pasan (`pytest`).
- [ ] PR de `modelos` a `main` con CI en verde y merge (avisar en el chat: "OCR real en main").

### 8.2 Datos — Databricks: capas y datos 🧱 (hitos H1 y H2)

#### 8.2.1 ⭐ Crear esquemas y volúmenes

Usa el catálogo que anotaron en 6.1 (aquí `workspace`). Si Ariela ya lo hizo en 6.4, solo verifica. Notebook `00_setup`:

```sql
%sql
CREATE SCHEMA IF NOT EXISTS workspace.g6_bronce;
CREATE SCHEMA IF NOT EXISTS workspace.g6_plata;
CREATE SCHEMA IF NOT EXISTS workspace.g6_oro;

CREATE VOLUME IF NOT EXISTS workspace.g6_bronce.crudos;
CREATE VOLUME IF NOT EXISTS workspace.g6_oro.artifacts;
```

Si el profesor les dio una external location de S3, en lugar de los `CREATE VOLUME` de arriba usen (con la URL anotada):

```sql
%sql
CREATE EXTERNAL VOLUME IF NOT EXISTS workspace.g6_bronce.crudos
  LOCATION 's3://NOMBRE-BUCKET/g6/bronce/';
CREATE EXTERNAL VOLUME IF NOT EXISTS workspace.g6_oro.artifacts
  LOCATION 's3://NOMBRE-BUCKET/g6/oro/artifacts/';
```

Con esto las capas quedan literalmente en S3, como en el diagrama. Las tablas de plata y oro también pueden ir a S3 si los esquemas se crean con `MANAGED LOCATION 's3://...'`.

#### 8.2.2 ⭐ Subir las fotos a bronce

1. Catalog → `workspace` → `g6_bronce` → Volumes → `crudos`.
2. Create directory → `fotos`.
3. Entra a `fotos` → Upload to this volume → arrastra las 5 fotos `.jpg` (y las nuevas que tomen). Sube los archivos originales, sin editarlos, porque bronce es una copia fiel.
4. Crea también los directorios `mem`, `fred`, `etiquetas` y `api_logs` (si no existen).

Ruta final de una foto: `/Volumes/workspace/g6_bronce/crudos/fotos/IMG_8271.jpg`.

#### 8.2.3 ⭐ Conectar el repo a Databricks (Git folder) — cada persona

Así los notebooks y el paquete viven en GitHub y Databricks los usa directo.

1. Barra izquierda → Workspace → tu carpeta de usuario → Create → Git folder.
2. URL: `https://github.com/TU_USUARIO/gasolina-mlops.git`.
3. Cambia a tu rama (`datos` o `modelos`) con el botón de la rama.
4. Para actualizar después de un push o merge: abre la carpeta → botón de la rama → Pull.

En cada notebook, la primera celda instala el paquete desde el repo:

```python
%pip install -e /Workspace/Users/TU_CORREO/gasolina-mlops
dbutils.library.restartPython()
```

(Si `-e` falla en serverless, usa `%pip install /Workspace/Users/TU_CORREO/gasolina-mlops` sin `-e`.)

#### 8.2.4 ⭐ Datos externos a bronce

a) Precios del MEM (histórico de Guatemala)

El MEM no tiene una API. Publica informes PDF ("Informe ejecutivo de precios de los combustibles") en su sitio, y cada informe trae una tabla de precios promedio de las últimas ~7 semanas para Super, Regular y Diésel (y precios de referencia vs monitoreados). Ejemplo de URL:
`https://mem.gob.gt/wp-content/uploads/2026/05/INFORME-EJECUTIVO-DE-PRECIOS-DE-LOS-COMBUSTIBLES-2026-05-27.pdf`

Pasos 💻:

1. En el navegador entra a mem.gob.gt → Hidrocarburos → Precios (o busca en Google "INFORME EJECUTIVO DE PRECIOS DE LOS COMBUSTIBLES site:mem.gob.gt").
2. Descarga un informe cada ~6 semanas, de enero 2025 a hoy (unos 12–15 PDF). Como cada uno trae 7 semanas, juntos cubren todo el periodo.
3. Guárdalos en `datos/mem/` sin renombrarlos.
4. Súbelos a `/Volumes/workspace/g6_bronce/crudos/mem/` (igual que las fotos).

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

Si el parser se complica con algún PDF, es válido completar a mano las semanas faltantes en el CSV y documentarlo ("curación manual de fuente externa"). Lo importante es tener la serie.

Anota también las fechas del subsidio ("Apoyo Social Temporal"): inicio el 28/04/2026 (Q5 gasolinas, Q8 diésel). Busquen en noticias cuándo terminó o cambió (los precios de julio en las fotos sugieren un cambio a mediados de julio). Guárdenlo en `datos/mem/eventos_subsidio.csv` y súbanlo también a `crudos/mem/`:

```csv
fecha_inicio,fecha_fin,producto,monto_q
2026-04-28,AAAA-MM-DD,gasolinas,5.00
2026-04-28,AAAA-MM-DD,diesel,8.00
```

b) FRED (precios internacionales, gratis y automatizable)

FRED (Reserva Federal de St. Louis) permite descargar CSV sin registrarse:

| Serie | Qué es | URL |
| --- | --- | --- |
| `DGASUSGULF` | Gasolina regular convencional, Costa del Golfo EE. UU. (USD/galón, diario) | `https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGASUSGULF` |
| `DDFUELUSGULF` | Diésel ULSD, Costa del Golfo (USD/galón, diario) | `https://fred.stlouisfed.org/graph/fredgraph.csv?id=DDFUELUSGULF` |
| `DCOILWTICO` | Petróleo WTI (USD/barril, diario) | `https://fred.stlouisfed.org/graph/fredgraph.csv?id=DCOILWTICO` |

Notebook `01_bronce_ingesta` 🧱: intenta descargarlos desde Databricks. Si la red del workspace lo bloquea, descárgalos en la Mac con el navegador y súbelos a `crudos/fred/`.

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

Checklist:

- [ ] En `crudos/` hay `fotos/`, `mem/` (PDF + subsidio), `fred/` (CSV), `etiquetas/` y `api_logs/`.
- [ ] Existe la tabla `g6_bronce.inventario`.

#### 8.2.5 ⭐ Bronce → Plata

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

#### 8.2.6 ⭐ Plata → Oro

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

Orden recomendado para Datos: primero MEM y FRED → `precios_mem`, `exogenas_diarias` → `features_forecast` (lo necesita Modelos para el pronóstico, hito H1). Después, cuando el OCR real esté en `main`, se vuelve a correr `02_plata` y `03_oro` para las fotos.

Checklist:

- [ ] Tablas en plata (`lecturas_ocr`, `precios_mem`, `exogenas_diarias`) y oro (`precios_estacion`, `comparacion_mem`, `features_forecast`).
- [ ] `reglas.json` e `historico.json` en `g6_oro/artifacts/` (reemplazando los demo).
- [ ] PR a `main` y Pull en el Git folder de Databricks.

#### 8.2.7 Cómo revisar que las capas quedaron bien 🧱

```sql
%sql
SELECT combustible, COUNT(*), MIN(precio), MAX(precio), AVG(score_confianza)
FROM workspace.g6_plata.lecturas_ocr GROUP BY combustible;

SELECT * FROM workspace.g6_oro.comparacion_mem ORDER BY fecha_foto;

DESCRIBE HISTORY workspace.g6_plata.lecturas_ocr;   -- versiones (time travel) para el reporte
```

Toma capturas: sirven para el reporte (trazabilidad y versionado de datos).

### 8.3 Modelos — Experimentos y pronóstico en Databricks 🧱 (hito H2)

#### 8.3.1 Experimentos de OCR en MLflow

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

Sube `etiquetas.csv` a `crudos/etiquetas/`.

Para ver los resultados: barra izquierda → Experiments → `g6_ocr_gasolina`. Selecciona varias corridas → Compare. Toma capturas.

#### 8.3.2 Pronóstico de precios

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

Checklist:

- [ ] Experimentos de OCR y de forecast visibles en MLflow con varias corridas.
- [ ] Modelos registrados en Unity Catalog (Catalog → `g6_oro` → Models).
- [ ] `ocr_config.json`, `forecast.joblib`, `forecast_meta.json` y `predicciones.json` en `g6_oro/artifacts/` (reemplazando los demo).

### 8.4 Producción — API completa, página, CI y tráfico simulado 💻 (hito H2)

Todo se prueba en la Mac con los artifacts demo; cuando lleguen los reales, solo se corre `gasolina-sync descargar`.

#### 8.4.1 ⭐ API completa

```
PROMPT PARA CLAUDE CODE
Revisa y completa src/gasolina/api/app.py (ya existe una versión mínima) con FastAPI:
- Al iniciar, carga artifacts desde ARTIFACTS_DIR (default ./artifacts): ocr_config.json,
  reglas.json, forecast_meta.json, predicciones.json, historico.json, monitoreo.json.
  Si falta alguno, arranca igual con los de artifacts_demo y lo reporta en /health.
  Los JSON se recargan si cambia su fecha de modificación.
- GET /health → status, versión del paquete, origen y versión de cada artifact, modo de
  extracción (stub|real), fecha de carga.
- POST /extraer (multipart, campo "foto", JPG/PNG/HEIC, máx 15 MB) → JSON de extraer_precios
  (contrato 4.1) usando ocr_config.json y la referencia MEM de reglas.json; sin
  detecciones_crudas por defecto (parámetro ?debug=true las incluye).
- GET /pronostico → contenido de predicciones.json.
- GET /metricas → contadores en memoria: total de peticiones, % con score >= umbral,
  latencia p50/p95.
- Cada llamada a /extraer se registra (sin guardar la imagen, contrato 4.3) en
  logs/predicciones_YYYYMMDD.jsonl.
- Sirve src/gasolina/api/static/index.html en "/".
- Manejo de errores claro (400 si no es imagen, 500 con mensaje).
Agrega tests con fastapi.testclient (health y extraer con una imagen de ../datos si existe).
```

Prueba local 💻:

```bash
gasolina-api
# en otra terminal:
curl http://localhost:8000/health
curl -F "foto=@../datos/IMG_8271.jpg" http://localhost:8000/extraer
```

También puedes abrir `http://localhost:8000/docs` en el navegador: FastAPI genera una página para probar la API.

#### 8.4.2 ⭐ Interfaz web con todo (extracción, pronóstico y dashboard de monitoreo)

La interfaz es la "cara" del proyecto y concentra todo en un solo lugar. Además, Databricks tiene su propio dashboard (sección 8.5.3). Son dos públicos distintos: la interfaz es para el usuario y para la demo, y el de Databricks es el tablero interno del equipo de datos.

Primero, endpoints extra en la API para alimentar el dashboard:

```
PROMPT PARA CLAUDE CODE
Agrega o completa en src/gasolina/api/app.py:
- GET /monitoreo/produccion → calculado en vivo desde logs/*.jsonl: peticiones por día
  (últimos 30 días), % con score alto/medio/bajo, % de cada validación fallida, latencia
  p50/p95 por día, % de coincidencia ruta A vs ruta B, combustible despachado más frecuente,
  últimas 20 lecturas (sin imagen).
- GET /monitoreo/modelo → lee artifacts/monitoreo.json (exportado por el job de monitoreo de
  Databricks, contrato 4.2): error del pronóstico en producción vs validación, drift vs MEM,
  estado de alertas, fecha del último reentrenamiento, versión champion.
- GET /historico → lee artifacts/historico.json (exportado desde oro) y le agrega
  predicciones.json: serie semanal MEM por combustible + precios leídos de fotos + predicciones.
Todos deben responder aunque falten archivos (listas vacías y un campo "disponible": false).
```

Luego, la página:

```
PROMPT PARA CLAUDE CODE
Crea src/gasolina/api/static/index.html (reemplaza la versión sencilla): una sola página,
sin frameworks pesados (HTML + CSS + JS vanilla; Chart.js desde CDN con versión fija está
bien), en español con ortografía perfecta, con 4 pestañas:

1. "Leer foto": arrastrar/elegir una foto, miniatura, botón que llama a /extraer. Mostrar:
   - Ruta A (arriba): total, galones, precio calculado y qué combustible coincide.
   - Ruta B (abajo): 4 tarjetas (Diesel, Regular, Super, V-Power) con precio, fuente
     (ruta_B / ambas / corregido_por_ruta_A / inferido) como etiqueta de color, y semáforo
     según score_confianza.
   - Validaciones con ✓/✗ y mensaje; fecha y ubicación de la metadata (link a mapa).
2. "Pronóstico": predicción de la próxima semana por combustible (/pronostico) y gráfica
   histórica (/historico) con la serie MEM, los puntos de las fotos y la predicción.
3. "Monitoreo": dashboard con KPIs (peticiones hoy, % confianza alta, latencia p95,
   % coincidencia A vs B), gráfica de peticiones y latencia por día, barras de validaciones
   que más fallan, tabla de últimas lecturas, y bloque "Salud del modelo" desde
   /monitoreo/modelo (error en producción vs validación, drift vs MEM, alertas activas en
   rojo, versión y fecha de reentrenamiento). Se refresca solo cada 60 s.
4. "Acerca de": diagrama simple de la arquitectura (bronce → plata → oro → API), estado de
   /health, versiones de artifacts (con un aviso visible si el origen es "demo") y créditos
   del Grupo 6.

Diseño limpio y profesional, responsive, colores sobrios inspirados en una estación de
servicio (sin logos ni marcas de Shell), modo claro y oscuro. Cada pestaña debe verse bien
aunque un endpoint responda "disponible": false (mensaje amable, no pantalla rota).
```

#### 8.4.3 ⭐ CI/CD con GitHub Actions 🐙

```
PROMPT PARA CLAUDE CODE
Revisa .github/workflows/ci.yml y deploy.yml (ya existen). Asegúrate de que:
1. ci.yml en cada push y PR a main instala Python 3.11, el paquete con [api,dev], corre ruff
   y pytest; y solo en push a main, si pasa lo anterior, construye la imagen linux/amd64 y la
   publica en ghcr.io/<owner en minúsculas>/gasolina-mlops:latest y :<sha>.
2. deploy.yml es SOLO manual (workflow_dispatch), porque el servidor solo está encendido en
   clase; usa los secrets SSH_HOST, SSH_USER y SSH_PRIVATE_KEY y corre scripts/deploy.sh.
   Que falle con un mensaje claro si no puede conectarse ("¿El servidor está encendido?").
Explícame en 5 líneas cómo verificar que la imagen quedó pública en GHCR.
```

Si el deploy automático no se pudo configurar el martes, basta con el CI de tests e imagen y explicar el CD en el reporte.

#### 8.4.4 ⭐ Tráfico simulado para que Datos construya el monitoreo

```
PROMPT PARA CLAUDE CODE
Corre la API localmente (gasolina-api o docker compose up) y usa scripts/generar_trafico.py
con --repeticiones 5 sobre ../datos para generar logs de producción simulados. Luego, con mi
.env cargado, corre gasolina-sync subir-logs para que lleguen a
/Volumes/<cat>/g6_bronce/crudos/api_logs/. Muéstrame cuántas líneas se generaron y qué
archivos se subieron. Esto sirve para que la persona de Datos construya el monitoreo antes
de que exista tráfico real en el servidor.
```

Avisa en el chat: "Logs simulados en `crudos/api_logs/`".

### 8.5 Datos — Jobs, monitoreo y dashboard 🧱 (hitos H2 y H3)

#### 8.5.1 ⭐ Job del pipeline (entrenamiento)

1. Barra izquierda → Jobs & Pipelines → Create → Job.
2. Nombre: `g6_pipeline_semanal`.
3. Tareas, todas de tipo Notebook, con source Git provider (repo `gasolina-mlops`, rama `main`) y compute serverless:
   1. `ingesta` → `notebooks/01_bronce_ingesta`
   2. `plata` → `notebooks/02_plata` (depende de ingesta)
   3. `oro` → `notebooks/03_oro` (depende de plata)
   4. `forecast` → `notebooks/05_forecast` (depende de oro)
4. Schedule: semanal, lunes 7:00 a. m. (zona America/Guatemala), porque el MEM publica precios semanalmente.
5. Notifications: correo On failure (de las 3 personas).
6. Run now para probarlo. Toma una captura del grafo de tareas en verde.

#### 8.5.2 ⭐ Job de monitoreo de producción

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

Crea el Job `g6_monitoreo_diario` (una tarea: `06_monitoreo`, diario a las 8:00, alerta por correo On failure). Pruébalo con los logs simulados de 8.4.4.

Este es el ciclo completo de MLOps: producción genera logs → bronce → monitoreo en oro → alerta → reentrenamiento. En el servidor, la subida de logs la hace el cron de la sección 7.2 y `fin_de_clase.sh`.

#### 8.5.3 ⭐ Dashboard de monitoreo

1. Barra izquierda → Dashboards → Create dashboard.
2. Pestaña Data → Add data source → tablas `g6_oro.monitoreo_diario`, `g6_oro.comparacion_mem`, `g6_oro.predicciones` y `g6_plata.precios_mem`.
3. Visualizaciones sugeridas (en la pestaña del lienzo, Add a visualization):
   - Línea: precio MEM semanal por combustible + puntos de las fotos (histórico).
   - Línea: pronóstico vs real.
   - KPIs (counter): peticiones del día, % confianza alta, latencia p95.
   - Barras: validaciones que más fallan.
   - Tabla: últimas lecturas con score bajo (para revisión manual).
4. Publish. Toma capturas.

Si quieren ayuda con las consultas SQL de cada gráfica:

```
PROMPT PARA CLAUDE CODE
Dame las consultas SQL (Databricks SQL) para estas visualizaciones de un dashboard AI/BI,
usando las tablas <cat>.g6_oro.monitoreo_diario, comparacion_mem, predicciones y
<cat>.g6_plata.precios_mem: [pega la lista de la sección de dashboard]. Para cada una dime qué
tipo de gráfica elegir y qué columna va en cada eje.
```

### 8.6 ⭐ Integración del jueves en la noche (hito H3): simulacro completo en la Mac

El objetivo es que el viernes no haya sorpresas: lo que corre aquí es exactamente lo que va a correr en el servidor (misma imagen de GHCR, mismo `.env`, mismos scripts).

Responsable: Ariela, con los otros dos en llamada.

1. Todos los PR están en `main` y el CI está en verde (imagen nueva publicada).
2. 🧱 Datos corre el job `g6_pipeline_semanal` completo y queda en verde.
3. 🧱 Los 7 artifacts reales están en `g6_oro/artifacts` (ninguno con `"origen": "demo"`).
4. 💻 Ariela, en la carpeta del repo:

```bash
git checkout main && git pull
set -a; source .env; set +a
docker compose pull                                         # la misma imagen que usará el servidor
docker compose run --rm --no-deps -e ARTIFACTS_DIR=/app/artifacts api gasolina-sync descargar
docker compose up -d
curl -s localhost:8000/health | python3 -m json.tool        # origen: databricks, modo: real
python scripts/generar_trafico.py --url http://localhost:8000 --carpeta ../datos --repeticiones 3
```

5. 💻 Abrir `http://localhost:8000` y revisar las 4 pestañas con datos reales.
6. 💻 `docker compose run --rm --no-deps api gasolina-sync subir-logs` → 🧱 Datos corre `g6_monitoreo_diario` → 💻 `gasolina-sync descargar` otra vez → la pestaña "Monitoreo" muestra la salud del modelo.
7. Si `docker` no existe en la Mac: mismo simulacro con `gasolina-api` y `ARTIFACTS_DIR=./artifacts`.
8. Grabar con QuickTime un video de respaldo de la demo local (por si el viernes el servidor falla).
9. `main` se congela. Cualquier cambio después de esto necesita el visto bueno de las 3 personas.

Checklist "listo para el viernes":

- [ ] Simulacro completo sin errores con artifacts reales.
- [ ] Job semanal y job de monitoreo en verde.
- [ ] Dashboard de Databricks publicado.
- [ ] Video de respaldo grabado.
- [ ] Guion del video de la demo escrito (sección 9.2).

---

## 9. Fase 3 — Viernes en la clase ▶ (1:30 h)

Meta: desplegar la versión final, generar tráfico real y llevarse todas las evidencias, porque puede ser la última vez que el servidor esté encendido.

### 9.1 Guion minuto a minuto

| Minuto | Quién | Dónde | Qué hacer | Evidencia |
| --- | --- | --- | --- | --- |
| 0–3 | Ariela | 🧑‍🏫 | Confirmar con el profesor si el servidor estará encendido el día de la presentación. | Respuesta anotada. |
| 3–15 | Ariela | 🌊 | `ssh gasolina` → `cd ~/apps/gasolina-mlops && bash scripts/deploy.sh` (o correr el workflow `deploy` desde GitHub y mirar). | `/health` con `origen: databricks` y `modo: real`. |
| 15–25 | Modelos | 💻 | `python scripts/generar_trafico.py --url http://159.65.111.14:8000 --carpeta ../datos --repeticiones 3` y subir fotos nuevas desde la página. | Tabla de resultados en la Terminal. |
| 15–30 | Datos y Ariela | 💻 | Capturas: las 4 pestañas de la página, `/docs`, `/health`, `docker compose ps`, workflow `deploy` en verde. | Carpeta `evidencias/clase_viernes/`. |
| 30–45 | Todos | 💻 | Grabar el video de la demo en vivo (2–3 min, guion 9.2) con la URL pública visible. | Video `.mov`. |
| 45–55 | Ariela | 🌊 | `bash scripts/fin_de_clase.sh` (sube los logs reales a bronce). | `.jsonl` del día en `crudos/api_logs/`. |
| 55–70 | Datos | 🧱 | Correr `g6_monitoreo_diario` con los logs reales; refrescar el dashboard. | Captura del job y del dashboard con `entorno = servidor`. |
| 70–80 | Ariela | 🌊 | `docker compose run --rm --no-deps api gasolina-sync descargar` para traer el `monitoreo.json` nuevo; la pestaña "Monitoreo" se actualiza sin reiniciar. | Captura de "Salud del modelo" en vivo. |
| 80–90 | Ariela | 🌊 | `bash scripts/fin_de_clase.sh` final; copiar a la Mac `logs/` y el estado. Dejar la API corriendo (se levanta sola al encender el servidor). | `scp -r gasolina:~/apps/gasolina-mlops/logs evidencias/clase_viernes/` |

Si algo falla en el despliegue y no se arregla en 10 minutos: se hace la demo con la imagen corriendo en la Mac (mismo contenedor) y se documenta. Las evidencias del martes demuestran que la infraestructura del servidor funciona.

### 9.2 Guion del video de la demo (2–3 minutos)

1. Mostrar la URL `http://159.65.111.14:8000` y la pestaña "Acerca de" con `/health` en verde.
2. "Leer foto": subir una foto conocida y una foto nueva; explicar ruta A, ruta B, fusión y validaciones.
3. "Pronóstico": predicción de la próxima semana y la gráfica histórica.
4. "Monitoreo": KPIs de las peticiones que se acaban de hacer y la salud del modelo.
5. Cortar a Databricks: capas, MLflow Compare, modelo champion, job y dashboard.

---

## 10. Fase 4 — Después del viernes ⏸: entregables y presentación

Como el profesor no dio formato, sigan el patrón del Caso de Estudio 2, que es lo que él suele pedir, y agreguen la demo.

### 10.1 ⭐ Lista de entregables

- [ ] Repositorio de GitHub con README completo: qué es, arquitectura, cómo correrlo local, cómo desplegar y resultados.
- [ ] Diagrama de arquitectura (Excalidraw, como el del profesor, o draw.io) con: fuentes → bronce → plata → oro → MLflow/registro → artifacts → GitHub Actions/GHCR → servidor (Docker/FastAPI) → usuario, más el lazo de logs → monitoreo → alerta.
- [ ] Reporte (PDF o notebook) con la estructura de 10.2.
- [ ] Notebooks de Databricks exportados (File → Export → HTML o .ipynb) en `notebooks/`.
- [ ] Capturas: tablas por capa, `DESCRIBE HISTORY`, experimentos de MLflow (Compare), modelo registrado, Job en verde, dashboard, API respondiendo, página HTML, workflow de deploy.
- [ ] URL de la demo en vivo: `http://159.65.111.14:8000` (funciona solo cuando el servidor está encendido; la API arranca sola).
- [ ] ✨ Video corto (2–3 min) de la demo: subir foto → precios → pronóstico → dashboard.

### 10.2 Estructura del reporte

1. Resumen ejecutivo (media página): problema, solución y resultados clave en números.
2. Business understanding: reutilicen el del Caso 1 (ya lo tienen hecho) y actualícenlo.
3. Datos: las 3 fuentes (imagen, metadata, externas). Por qué cada una y sus limitaciones (solo 5 fotos de una estación, formato PDF del MEM, tipo de cambio constante).
4. Arquitectura: diagrama + explicación por capa y dónde vive cada cosa. Lab (Databricks) vs producción (droplet), y por qué se separan (Actividad 5: ambientes).
5. Modelo de extracción: OCR + reglas, experimentos y tabla comparativa de MLflow, métricas finales, ejemplos de aciertos y errores con imágenes.
6. Modelo de pronóstico: features, validación temporal, comparación vs baseline, efecto del subsidio.
7. Despliegue: Docker, imagen en GHCR, API, endpoints, cómo se actualiza (sync de artifacts, `deploy.sh`, CI/CD) y cómo se diseñó para un servidor que solo está encendido por ventanas (arranque automático, todo probado antes en local con la misma imagen). Eso es un buen punto de ingeniería para el reporte.
8. Monitoreo: métricas, umbrales, alertas, dashboard y el ciclo de retroalimentación.
9. Conclusiones y trabajo futuro: más fotos y estaciones, fine-tuning de un detector de pantallas (YOLO) cuando haya datos, tipo de cambio del Banguat, otras marcas.
10. Referencias y link al repo.

```
PROMPT PARA CLAUDE CODE
Con base en el repo gasolina-mlops (lee el README, notebooks, config y los resultados que
te pego abajo), redacta el reporte final en español formal con ortografía perfecta,
siguiendo esta estructura: [pega la estructura del reporte]. Encabezado: "Grupo 6 — Alina
Carías, Marcos Díaz, Daniel Machic, Ignacio Méndez, Ariela Mishaan y Diego Soto". Usa tablas
para métricas. Deja marcadores [CAPTURA: ...] donde vayan capturas. Resultados: [pega aquí
las tablas de MLflow, métricas de OCR y forecast, y lo que salió del monitoreo].
```

### 10.3 Qué hace que esto saque 100 (lo que el profesor va a buscar)

| Criterio | Dónde se demuestra |
| --- | --- |
| Capas bronce, plata y oro reales y con propósito claro | Sección 8.2 + capturas |
| Databricks como laboratorio | Notebooks, Git folder, MLflow |
| Experimentación seria (no "funcionó y ya") | Comparación de motores de OCR y de modelos vs baseline en MLflow |
| Modelo versionado y registrado | Unity Catalog Models con alias champion |
| Producción separada del lab | Droplet con Docker y API pública |
| Automatización | Jobs programados, `deploy.sh`, CI en GitHub Actions, imagen en GHCR |
| Monitoreo con alertas | Job de monitoreo + dashboard + correo al fallar |
| Uso de metadata y variables exógenas | EXIF (fecha/GPS), MEM, FRED, subsidio |
| Reproducibilidad | Paquete con entrypoints, requirements, Docker, README |
| Honestidad técnica | Limitaciones documentadas (pocas fotos, una estación, servidor por ventanas) |

### 10.4 Ensayo de la demo (15 minutos antes de presentar)

Si el servidor está encendido:

```bash
ssh gasolina "cd ~/apps/gasolina-mlops && docker compose ps && curl -s localhost:8000/health"
```

- Abre `http://159.65.111.14:8000` y ten lista una foto que funcione bien y una nueva tomada por ustedes.
- Ten abiertas las pestañas: MLflow (Compare), el Job, el Dashboard y el repo.
- Plan B si el servidor está apagado o falla: en la Mac, `docker compose up -d` con la misma imagen y muestra `localhost:8000`, y luego el video grabado el viernes en el servidor.

---

## 11. Problemas comunes

| Problema | Causa probable | Solución |
| --- | --- | --- |
| `Permission denied (publickey)` | La llave no está en el servidor | Revisar con el profesor (ya lo resolvimos una vez). |
| `ssh: connect to host ... timed out` | El servidor está apagado | Normal fuera de clase. Seguir con trabajo ⏸. |
| `%pip install` falla en Databricks | Ruta del repo mal escrita | Copia la ruta exacta: clic derecho en la carpeta → Copy path. |
| `PERMISSION_DENIED` al crear esquema o volumen | Sin permisos en ese catálogo | Pedir al profesor un catálogo o esquema para el equipo. |
| `requests` no descarga FRED en Databricks | Internet restringido en el workspace | Descargar el CSV en la Mac y subirlo a `crudos/fred/`. |
| El OCR lee `3809` sin punto | Típico en LCD | `normalizar_numero` ya inserta el punto. Revisar los tests. |
| `docker: permission denied` | Usuario fuera del grupo docker | Pedir al profesor o dejar que `deploy.sh` use el modo venv. |
| `docker compose pull` dice `denied` o `unauthorized` | La imagen en GHCR es privada | 🐙 Packages → Package settings → Change visibility → Public. Mientras tanto, `deploy.sh` la construye en el servidor. |
| `exec format error` al correr la imagen | Imagen construida en una Mac con chip M (arm64) | Usar solo la imagen que construye GitHub Actions (amd64). |
| La API funciona en el servidor pero no desde la Mac | Puerto cerrado | Pedir abrir el 8000 o usar el túnel `ssh -L`. |
| `gasolina-sync` dice 401/403 | Token vencido o mal copiado | Generar otro token y actualizar `.env`. |
| `/health` dice `origen: demo` | No se descargaron los artifacts reales | Correr `gasolina-sync descargar` y revisar que estén en `g6_oro/artifacts`. |
| Conflicto de Git en un archivo | Dos personas editaron lo mismo | Revisar la tabla de dueños (3.1); lo resuelve el dueño del archivo. |
| Un compañero cambió algo en el servidor y se rompió | Usuario compartido | Siempre desplegar con `deploy.sh` desde `main`, nunca editar archivos a mano en el servidor. |

Para cualquier error, pégaselo a Claude Code:

```
PROMPT PARA CLAUDE CODE
Estoy en el paso [X.Y] del instructivo [general / de mi rol]. Corrí: [comando]. Me salió:
[error completo]. Estoy en [mi Mac / el servidor / Databricks]. Explícame qué significa y
dame el arreglo paso a paso.
```

---

## 12. Preguntas para el profesor (hoy al inicio de la clase, en persona)

1. ¿Va a encender el servidor el viernes? ¿Y el día de la presentación final? ¿A qué hora exactamente?
2. ¿El usuario `cc3105` puede usar Docker? ¿Está abierto el puerto 8000 del droplet (o cuál podemos usar)?
3. ¿Podemos agregar una llave SSH para GitHub Actions al usuario `cc3105` (para el deploy automático)?
4. ¿Podemos usar un token personal de Databricks desde el droplet para sincronizar artifacts?
5. ¿Nos confirma el formato de entrega (reporte, repo, demo, presentación) y la fecha?
6. En Databricks, ¿hay una external location de S3 para el equipo, o usamos volúmenes administrados?
7. ¿Nos va a dar más imágenes o usamos las 5 + las que tomemos nosotros?
8. Si el servidor no va a estar encendido en la presentación, ¿acepta la demo grabada en vivo el viernes + la misma imagen corriendo en local?

---

### Fuentes de datos externas

- MEM, Informe ejecutivo de precios de los combustibles (ejemplo, 27/05/2026): https://mem.gob.gt/wp-content/uploads/2026/05/INFORME-EJECUTIVO-DE-PRECIOS-DE-LOS-COMBUSTIBLES-2026-05-27.pdf
- MEM, Precios de combustibles nacionales: https://mem.gob.gt/que-hacemos/hidrocarburos/comercializacion-downstream/precios-combustible-nacionales/
- FRED (St. Louis Fed): series DGASUSGULF, DDFUELUSGULF, DCOILWTICO — https://fred.stlouisfed.org/
- Límites de Databricks Free Edition (por si el workspace es de ese tipo): https://docs.databricks.com/aws/en/getting-started/free-edition-limitations
