# gasolina-mlops

Lectura de precios de gasolina desde fotos de bombas + pronóstico semanal, con arquitectura
medallion en Databricks y API en producción (Docker + FastAPI en DigitalOcean).
Proyecto final de ML Engineering (CC3105) — Grupo 6.

Documentación completa: [docs/INSTRUCTIVO_GENERAL.md](docs/INSTRUCTIVO_GENERAL.md) (los contratos entre
roles están en la sección 4) y [docs/instructivos_equipo/](docs/instructivos_equipo/).

## Ambiente local

```bash
python3.11 -m venv .venv && source .venv/bin/activate
pip install -e ".[api,dev]"
pytest
gasolina-api                     # http://localhost:8000  (docs: /docs)
```

La carpeta `../datos/` (fotos) vive fuera del repo.

## Comandos

| Comando | Qué hace |
| --- | --- |
| `gasolina-extraer RUTA` | Lee los precios de una foto o carpeta e imprime JSON (contrato 4.1). |
| `gasolina-evaluar` | Compara contra `../datos/etiquetas.csv` (pendiente: Modelos). |
| `gasolina-sync descargar` | Artifacts de `GOLD_ARTIFACTS_PATH` → `ARTIFACTS_DIR` (+ `manifest.json`). |
| `gasolina-sync subir-logs` | `logs/*.jsonl` nuevos → `BRONZE_LOGS_PATH`. |
| `gasolina-api` | API en `0.0.0.0:8000`. |

Para sync en la Mac: `cp .env.example .env`, llénalo y luego
`set -a; source .env; set +a; ARTIFACTS_DIR=./artifacts gasolina-sync descargar`.

## Endpoints

`GET /` página · `GET /health` · `POST /extraer` (campo `foto`, `?debug=true`) · `GET /pronostico` ·
`GET /historico` · `GET /metricas` · `GET /monitoreo/produccion` · `GET /monitoreo/modelo`.

Si `ARTIFACTS_DIR` no tiene un artifact, la API usa el de `artifacts_demo/` y `/health` lo indica.

## Servidor

```bash
bash scripts/servidor_check.sh   # qué hay en el servidor
bash scripts/deploy.sh           # despliega (docker o venv, autodetecta)
bash scripts/fin_de_clase.sh     # sube logs y muestra estado
python scripts/generar_trafico.py --url http://IP:8000 --carpeta ../datos --repeticiones 3
```

## Estructura y dueños

| Rol | Archivos |
| --- | --- |
| Producción | `pyproject.toml`, `config/`, `src/gasolina/api/`, `sync.py`, `config.py`, `cli.py` (sync/api), `docker/`, `scripts/`, `.github/`, `artifacts_demo/`, `tests/test_api.py`, `tests/test_contratos.py`, `docs/` |
| Modelos | `metadata.py`, `ocr.py`, `reglas.py`, `extraccion.py`, `forecast.py`, `cli.py` (extraer/evaluar), `notebooks/04*`, `05*` |
| Datos | `externos.py`, `features.py`, `notebooks/00*`, `01*`, `02*`, `03*`, `06*` |
