# API — Equipo 6

API REST (FastAPI) sobre la capa **Oro**. Código: [`src/gasolina/api/app.py`](../src/gasolina/api/app.py)
y lectura de Oro en [`src/gasolina/oro.py`](../src/gasolina/oro.py). Swagger en `/docs`.

## Panel web de monitoreo

La ruta `/` sirve **Octano**, la interfaz HTML del observatorio: precios por
combustible, evolución semanal, predicciones, comparación con la línea base,
estado de las tablas y exploración del histórico. Incluye filtros por combustible
y fechas, paginación, selección de series y periodo del gráfico, actualización
manual y exportación CSV de los registros filtrados.

El archivo editable es [`index.html`](../src/gasolina/api/static/index.html).
CSS, JavaScript y gráficos SVG están incluidos en el mismo HTML, sin CDN ni
dependencias de frontend. Se adapta a escritorio y móvil. Los datos provienen
de los endpoints de esta API; no lleva precios ni resultados prefijados.
La interfaz identifica las fuentes de ejemplo y muestra errores de conexión
sin sustituirlos por cifras inventadas.

Para abrirlo localmente en Windows:

```powershell
.venv/Scripts/gasolina-api.exe
```

Visitar `http://localhost:8000/`. Abrir el archivo directamente permite ver la
estructura, pero para cargar información se necesita servirlo desde la API.
En el servidor se publicará en `http://159.65.111.14:8000/` después del despliegue
por la responsable de SSH. No requiere un hosting separado del backend.

| Endpoint | Qué devuelve |
| --- | --- |
| `GET /health` | Estado del servicio, fuente de Oro (`s3`, `databricks` o `demo`) y filas por tabla |
| `GET /precios/actual` | Último precio semanal (martes a lunes) de super, regular y diésel |
| `GET /precios?combustible=diesel&desde=2026-10-01&hasta=2026-11-30&limit=100&offset=0` | Histórico semanal con variación y dirección |
| `GET /prediccion?combustible=super` | Predicción de la semana siguiente (`sube`, `baja`, `se_mantiene`) con probabilidad |
| `GET /modelo/metricas` | Exactitud y F1 del modelo frente a la línea base |

## Entorno aislado: uv (`pyproject.toml` + `uv.lock`)

En el Droplet no se puede usar Docker: requiere instalar paquetes del sistema con sudo, y el
enunciado lo prohíbe. Por eso usamos **uv**, que se instala en el usuario (`~/.local/bin`) y crea
un entorno virtual con las versiones exactas de `uv.lock`:

```bash
uv sync --frozen --extra api
cp .env.example .env && chmod 600 .env   # llenar credenciales de solo lectura
.venv/bin/gasolina-api
```

La imagen Docker (`docker/Dockerfile`) también existe: GitHub Actions la construye y la publica en
GHCR en cada push a `main`, y sirve para correr la API igual en cualquier máquina con Docker.

## Despliegue y persistencia

`bash scripts/deploy.sh` en el Droplet (o el workflow `deploy` de GitHub Actions): `git pull`,
`uv sync`, reinicia la API con `nohup` (sigue corriendo al cerrar SSH) y agrega `@reboot` al
crontab para que arranque sola si el servidor se reinicia. Espera a que `/health` responda.

## Credenciales

`.env` en la raíz del repo, con permisos `600`, nunca en Git. Variables en [`.env.example`](.env.example).
La API lee Oro con credenciales **de solo lectura**.

## Pruebas

- `pytest` (en el CI): endpoints, filtros, errores y contratos con tablas Oro de ejemplo.
- `BASE_URL=http://159.65.111.14:8000 bash tests/consultas_api.sh`: prueba de usuario final.
