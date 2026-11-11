# Guía de rol: Producción y coordinación (v3)

Proyecto Final ML Engineering · Equipo 06 (confirmar) · Responsable: Ariela

Esta guía es tu lista de tareas en orden. El mapa completo (arquitectura, contratos, calendario y rúbrica) está en `INSTRUCTIVO_GENERAL.md` v3. Los contratos de la sección 5 son obligatorios para todos.

---

## 1. Tu rol en una tabla

| Qué | Detalle |
| --- | --- |
| Entregas | Repo `equipo-06-gasolina-gt` (estructura, README, `.gitignore`), API en el Droplet (20 pts de la rúbrica), CI/CD, `tests/consultas_api.sh`, diagrama de arquitectura, coordinación de hitos y de la presentación. |
| Dependes de | Datos y Modelos: tablas Oro reales (semana 3). Catedrático: puerto, credenciales de solo lectura de S3 y permisos. |
| Dependen de ti | Todos: repo reorganizado (esta semana), `config.yaml`, `pyproject.toml` y `uv.lock`. |
| Tus archivos | `pyproject.toml`, `uv.lock`, `config/`, `api/`, `src/gasolina/api/`, `src/gasolina/oro.py`, `sync.py`, `config.py`, `docker/`, `scripts/`, `.github/`, `tests/test_api.py`, `tests/consultas_api.sh`, `docs/arquitectura.*`, `README.md` |
| Tu rama | `produccion` |

**Se entrega la próxima semana** (confirmar el día; el plan supone el martes 17). Tu plan día por día:

| Cuándo | Qué |
| --- | --- |
| Mar 10 (noche) | Preguntas al catedrático, reorganizar y renombrar el repo (2.3), rotar el token. |
| Mié 11 – Jue 12 | Tablas Oro de ejemplo y API v3 completa con pruebas (sección 3). |
| Vie 13 – Sáb 14 | Credenciales de solo lectura, API leyendo Oro real, despliegue final en el Droplet (secciones 4 y 5). |
| Dom 15 – Lun 16 | Diagrama, README, resumen para el jurado (48 h antes), plan B grabado, ensayo (sección 6). |

Lo que ya está hecho:

- [x] Repo con paquete, API mínima, Docker y 21 pruebas; CI en verde; imagen pública en GHCR.
- [x] Droplet: `deploy.sh` en modo venv con uv, API en el puerto 8000, `@reboot` y cron horario.
- [x] Workflow `deploy` de GitHub Actions en verde (llave `gha_deploy` agregada).
- [x] Sincronización con Databricks probada.

---

## 2. Semana 1 — Ahora mismo

### 2.1 ⭐ Preguntas al catedrático (hoy)

Las 9 preguntas están en la sección 13 del general. Anota las respuestas en la sección 2 del general y avisa en el chat.

### 2.2 ⭐ Revisar qué se puede leer en S3 🧱 (5 min)

```sql
%sql
LIST 's3://cc3105-cusn-869227452861-us-east-2-an/';
LIST 's3://cc3105-cusn-869227452861-us-east-2-an/fotos/';
```

Avisa en el chat si ya se ven las fotos (Datos lo necesita para `01_bronze`).

### 2.3 ⭐ Reorganizar y renombrar el repo 💻 🐙 (1 h)

Usa el prompt de la sección 7.3 del general en Claude Code (abierto en `Proyecto/gasolina-mlops`). Después:

1. 🐙 Settings → General → Repository name → `equipo-06-gasolina-gt` → Rename.
2. 💻 `git remote set-url origin https://github.com/ArielaMishaanCohen/equipo-06-gasolina-gt.git`
3. 🌊 En el Droplet, lo mismo dentro de `~/apps/gasolina-mlops` (la carpeta puede quedarse con su nombre).
4. 🐙 Settings → Collaborators: agrega a tus compañeros. Cada quien tiene que hacer commits propios (lo evalúa la rúbrica).
5. Crea las ramas `datos` y `modelos` desde `main` y avisa en el chat: "Repo v3 listo".

### 2.4 Rotar el token de Databricks

El token actual quedó visible en pantalla. Genera uno nuevo (Settings → Developer → Access tokens), revoca el anterior y actualiza el `.env` en la Mac y en el Droplet.

---

## 3. Semanas 1 y 2 — API completa con datos de ejemplo 💻

No necesitas esperar a nadie: construyes la API contra tablas Oro de ejemplo con el contrato exacto, y en la semana 4 solo cambias la ruta a S3.

### 3.1 ⭐ Tablas Oro de ejemplo

```
PROMPT PARA CLAUDE CODE
En el repo equipo-06-gasolina-gt, crea scripts/generar_oro_demo.py que escriba en
artifacts_demo/oro/ las 5 tablas Oro del contrato 5.4 de docs/instructivos/INSTRUCTIVO_GENERAL.md
como tablas Delta locales con la librería deltalake (agrégala al extra [api]):
precio_semanal, variacion_semanal, features_modelo, predicciones, metricas_modelo.
Datos sintéticos pero realistas: 30 semanas (martes a lunes) hasta la semana actual, para
super, regular y diesel (precios entre 30 y 40 Q/gal, super > regular > diesel con
variaciones semanales de ±0.50), direcciones con umbral 0.10, predicciones de la semana
siguiente con probabilidad y métricas de un modelo que supera levemente a la línea base.
Todas las tablas con una columna o propiedad que diga origen = "demo".
Corre el script y muéstrame un head de cada tabla.
```

### 3.2 ⭐ API v3

```
PROMPT PARA CLAUDE CODE
Reescribe src/gasolina/api/app.py para el contrato 5.5 de docs/instructivos/INSTRUCTIVO_GENERAL.md
(v3), manteniendo crear_app(), la página en "/" y /docs de FastAPI:
- Nuevo módulo src/gasolina/oro.py: lee las tablas Oro con deltalake. Si ORO_S3_PREFIX y las
  credenciales AWS_* están en el entorno, lee de s3://.../gold/<tabla>/ (solo lectura); si no,
  o si falla, usa artifacts_demo/oro/ y lo reporta. Caché en memoria con recarga cada
  ORO_TTL_SEGUNDOS (default 300) para no leer S3 en cada petición.
- GET /health: status, version, fuente_oro (s3|demo), filas y última semana de cada tabla,
  hora del servidor.
- GET /precios/actual, GET /precios (filtros combustible, desde, hasta; limit default 100,
  máximo 1000; offset), GET /prediccion (combustible opcional), GET /modelo/metricas.
- 400 con mensaje en español si combustible no es super|regular|diesel o si las fechas son
  inválidas; 404 si no hay datos.
- Quita /extraer, /pronostico, /historico y los endpoints de monitoreo de la v2 (o déjalos
  detrás de una bandera si siguen sirviendo para la demo de la foto: pregúntame).
- La API escucha en PUERTO (default 8006).
Actualiza tests/test_api.py (con las tablas demo) y tests/consultas_api.sh. Corre ruff y pytest.
```

### 3.3 ⭐ Página web para la demo y el QR

```
PROMPT PARA CLAUDE CODE
Reemplaza src/gasolina/api/static/index.html por una página de una sola pantalla, en español
con ortografía perfecta, pensada para abrirse en un teléfono (el jurado entra con un QR):
tarjetas con el precio actual de super, regular y diesel; la predicción de la semana
siguiente (flecha sube/baja/se mantiene, probabilidad y lo que diría la línea base); una
gráfica del histórico semanal (Chart.js desde CDN con versión fija) con filtro por combustible;
las métricas del modelo frente a la línea base; y el estado de /health con un aviso visible si
fuente_oro es "demo". HTML + CSS + JS sin frameworks, modo claro y oscuro, sin logos de
marcas. Que no se rompa si algún endpoint falla.
```

### 3.4 Pruebas y CI

- `tests/consultas_api.sh` muestra el precio actual y la predicción de los 3 combustibles (lo pide el enunciado).
- El CI ya corre ruff y pytest: eso da los puntos extra de "pruebas automatizadas de la API".

---

## 4. Semana 3 — Integración con Databricks

1. Pide al catedrático las credenciales AWS de solo lectura (bucket Oro, prefijo `equipo-06/`).
2. En la Mac, con esas credenciales en `.env`, prueba que `oro.py` lee las tablas reales que dejaron Datos y Modelos en `s3://cc3105-au-…/equipo-06/gold/`.
3. Cuando el Job esté listo, exporta su definición: Jobs → `equipo-06-pipeline` → ⋮ → View JSON → copia a `pipelines/job.json` (sin correos personales si el repo es público).

---

## 5. Semana 4 — Despliegue final en el Droplet 🌊

```bash
ssh gasolina
cd ~/apps/gasolina-mlops
git pull
nano .env        # agrega AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION=us-east-2,
                 # ORO_S3_PREFIX=s3://cc3105-au-869227452861-us-east-2-an/equipo-06/gold, PUERTO=80XX
chmod 600 .env
bash scripts/deploy.sh
```

O desde GitHub: Actions → `deploy` → Run workflow.

Verifica desde la Mac:

```bash
BASE_URL=http://159.65.111.14:80XX bash tests/consultas_api.sh
```

Criterio de aceptación: `/health` dice `fuente_oro: s3` y todos los endpoints devuelven datos reales.

Si el puerto cambia de 8000 a 80XX, el `@reboot` y `deploy.sh` lo toman del `.env`; revisa con `ss -tlnp | grep 80` que no quede la instancia vieja.

---

## 6. Semana 5 — Entregables (coordinas tú)

- [ ] `docs/arquitectura.drawio` + `.png` (prompt: pídele a Claude Code un diagrama draw.io con buckets por capa, workspace con cluster interactivo, job cluster y Job de 3 tareas, Droplet con la API, flujos SSH y HTTP, y GitHub Actions).
- [ ] README final con enlaces.
- [ ] Revisa que todos tengan commits.
- [ ] Resumen de una página para el jurado, **48 horas antes**, con la URL y el QR.
- [ ] Plan B: grabación de la demo (Job con fotos nuevas → `/prediccion` en el teléfono).
- [ ] Verifica la API en línea hasta la fecha de calificación.

---

## 7. Problemas comunes de tu rol

| Problema | Solución |
| --- | --- |
| `No module named 'gasolina'` en la Mac | `chflags -R nohidden .venv` (macOS marca como ocultos los archivos en Documents). |
| `deploy.sh` cae a modo venv | Normal: el Droplet no tiene Docker. Es la ruta oficial (uv). |
| `deltalake` no lee de S3 | Revisa `AWS_REGION=us-east-2` y que la ruta termine en la carpeta de la tabla (donde está `_delta_log/`). |
| El workflow `deploy` falla al conectar | ¿El Droplet está encendido? ¿Sigue la llave `gha_deploy` en `authorized_keys`? |
