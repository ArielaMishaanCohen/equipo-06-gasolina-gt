# Predicción del precio de la gasolina en Guatemala — Equipo 6

Proyecto final de ML Engineering (CC3105). Un pipeline de punta a punta que convierte **fotos de
bombas de gasolina** en datos, los organiza con la **arquitectura medallón** (Bronce → Plata → Oro)
en **AWS S3 + Databricks**, entrena un modelo que predice si el precio de **super, regular y diésel
sube, baja o se mantiene la semana siguiente**, y publica precios y predicciones en una **API REST**
en un Droplet de DigitalOcean.

- API: `http://159.65.111.14:8000` · Swagger: `/docs`
- Enunciado: [`docs/enunciado_cc3105_proyecto_final.pdf`](docs/enunciado_cc3105_proyecto_final.pdf)
- Instructivo del equipo: [`docs/instructivos/INSTRUCTIVO_GENERAL.md`](docs/instructivos/INSTRUCTIVO_GENERAL.md)
- Diagrama: [`docs/arquitectura.png`](docs/arquitectura.png) · Informe: [`docs/informe.pdf`](docs/informe.pdf) · Presentación: [`presentacion/`](presentacion/)

## Arquitectura

![Arquitectura](docs/arquitectura.png)

Editable en [app.diagrams.net](https://app.diagrams.net) con `docs/arquitectura.drawio`; se regenera con `python scripts/generar_arquitectura.py`. Resumen en texto:

```
s3://…-raw-…/img/  ──►  BRONCE  workspace.equipo_06_bronze  bronze.fotos_precios (Auto Loader, incremental)
 (xloc-raw: fotos del catedrático)│
                               ▼  OCR + 5 reglas de calidad + MERGE
                             PLATA   workspace.equipo_06_silver   silver.precios, silver.precios_rejected
                               │
                               ▼  semana martes-lunes, variación, features, modelo (MLflow)
                             ORO     workspace.equipo_06_gold     gold.precio_semanal, variacion_semanal,
                               │                                features_modelo, predicciones, metricas_modelo
                               ▼  SQL warehouse (token de Databricks en el .env del servidor)
                             API FastAPI en el Droplet (uv) ◄── usuario (HTTP) · equipo (SSH) · GitHub Actions (CD)
```

Databricks: Job `equipo-06-pipeline` con tres tareas encadenadas, cómputo serverless con entorno
versión 2, programación los martes a las 07:00 de Guatemala y alertas de fallo por correo.

**S3 y external locations.** Bronce lee las fotos directamente de la carpeta del catedrático
(`s3://cc3105-raw-…/img/`, 110 fotos de 2023 a 2026) por la external location `xloc-raw` de Unity
Catalog, con su storage credential (rol IAM). Las tablas se escriben en los esquemas
`workspace.equipo_06_*`. Cada notebook acepta una ruta `s3://` por capa (`ruta_tablas_bronze`,
`ruta_equipo_silver`, `ruta_equipo_oro`): con ella, sus tablas se crean como **externas** en el
prefijo `equipo6/` del bucket de su capa (`xloc-cusn`, `xloc-ag`, `xloc-au`). Al 16 de noviembre esas
tres ubicaciones siguen marcadas como solo lectura en el metastore (Databricks responde
`User cannot write to a read-only external location`), así que las tablas son gestionadas; en cuanto
se habilite la escritura basta con llenar esos tres parámetros del Job. La API lee Oro con el SQL
warehouse y ya trae la lectura directa desde S3 (`ORO_S3_PREFIX`) para ese momento.

## Estructura

| Carpeta | Contenido |
| --- | --- |
| `pipelines/` | Notebooks `00_setup.sql`, `01_bronze.py`, `02_silver.py`, `03_gold.py` y `job.json` |
| `src/gasolina/` | Paquete compartido por los notebooks y la API: extracción (OCR), reglas, features, modelo, lectura de Oro, API |
| `api/` | Punto de entrada de la API, `.env.example` y documentación del entorno |
| `config/config.yaml` | Valores que cambian (equipo, rutas S3, esquemas, umbral, puerto) |
| `tests/` | `pytest` (API y contratos) y `consultas_api.sh` (prueba de usuario final) |
| `scripts/` | `deploy.sh`, `fin_de_clase.sh`, `servidor_check.sh`, `generar_oro_demo.py`, `dbx_job.py` (aplicar, revertir o correr el Job) |
| `docker/` | Imagen de la API (la construye el CI y se publica en GHCR) |
| `docs/`, `presentacion/` | Diagrama, informe, enunciado, instructivos, diapositivas y resumen para el jurado |

## Reproducir el pipeline (Databricks)

1. Workspace → Create → Git folder con este repo.
2. Correr `pipelines/00_setup.sql` una vez (esquemas, Volume de trabajo y permisos). Las tablas las
   crea cada notebook si no existen.
3. Seleccionar el entorno serverless **versión 2** para las dependencias de estos notebooks.
   Ejecutar `01_bronze` → `02_silver` → `03_gold`, o el Job `equipo-06-pipeline` con **Run now**.
   La definición exportada está en `pipelines/job.json` y las evidencias en `docs/evidencias_job.md`.

## Desplegar la API (Droplet)

```bash
ssh <usuario>@159.65.111.14
git clone https://github.com/ArielaMishaanCohen/equipo-06-gasolina-gt.git ~/apps/gasolina-mlops
cd ~/apps/gasolina-mlops
cp .env.example .env && nano .env && chmod 600 .env   # credenciales de SOLO LECTURA
bash scripts/deploy.sh
```

`deploy.sh` instala las dependencias exactas de `uv.lock`, arranca la API con `nohup` (sigue viva al
cerrar SSH), agrega `@reboot` al crontab y espera a que `/health` responda. También se puede correr
desde GitHub: Actions → `deploy` → Run workflow.

**Por qué uv en el Droplet:** el servidor es compartido entre equipos y uv vive en el usuario
(`~/apps/gasolina-mlops/.venv`), sin tocar nada del sistema ni de los demás equipos, y garantiza las
mismas versiones con `pyproject.toml` y `uv.lock`. Arranca en segundos y `deploy.sh` lo deja vivo al
cerrar SSH y al reiniciar. Además existe la opción Docker: el CI construye la imagen y la publica en
GHCR, y `docker-compose.yml` la levanta con `restart: unless-stopped` (`deploy.sh --modo docker`).

## Desarrollo local

```bash
uv sync --extra api --extra dev      # o: python3.11 -m venv .venv && pip install -e ".[api,dev]"
uv run pytest
uv run gasolina-api                  # http://localhost:8000
BASE_URL=http://localhost:8000 bash tests/consultas_api.sh
```

Sin credenciales, la API usa las tablas Oro de ejemplo de `artifacts_demo/oro/` y `/health` lo dice
(`"fuente_oro": "demo"`). En una Mac, si aparece `No module named 'gasolina'`, corre
`chflags -R nohidden .venv`.

## CI/CD

- `ci.yml` (push y PR a `main`): ruff, pytest (pruebas automatizadas de la API) y, en `main`, imagen
  `ghcr.io/arielamishaancohen/gasolina-mlops` para `linux/amd64`.
- `deploy.yml` (manual): SSH al Droplet y `scripts/deploy.sh`.

## Equipo

Alina Carias, Marcos Diaz, Daniel Machic, Ignacio Mendez, Ariela Mishaan y Diego Soto.

El cierre de Modelos está en [`docs/modelos/CIERRE_MODELOS.md`](docs/modelos/CIERRE_MODELOS.md).
La responsable del servidor puede seguir
[`docs/DESPLIEGUE.md`](docs/DESPLIEGUE.md).
El informe y los PDF del jurado se regeneran con `python scripts/generar_entregables.py`.
