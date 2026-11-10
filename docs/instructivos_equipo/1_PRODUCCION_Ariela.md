# Instructivo de rol: Producción (y coordinación)

Proyecto Final ML Engineering · Grupo 6 · Responsable: Ariela

Este documento es tu lista de tareas en orden. El mapa completo (arquitectura, contratos, calendario) está en `INSTRUCTIVO_GENERAL.md`; aquí está solo lo tuyo, con los prompts completos para que no tengas que saltar entre archivos.

---

## 1. Tu rol en una tabla

| Qué | Detalle |
| --- | --- |
| Entregas | Repo base, API FastAPI, página web, Docker, imagen en GHCR, scripts de servidor, CI/CD, sync de artifacts y logs, despliegue en las dos clases. |
| Dependes de | Modelos (`extraer_precios` real, `ocr_config.json`, `predicciones.json`, `forecast_meta.json`) y Datos (`reglas.json`, `historico.json`, `monitoreo.json`). Mientras no lleguen, usas `artifacts_demo/` y el stub. |
| Dependen de ti | Todos dependen del repo base hoy. Datos depende de tus logs simulados (jueves a mediodía) para construir el monitoreo. |
| Tus archivos | `pyproject.toml`, `config/`, `src/gasolina/api/`, `sync.py`, `config.py`, funciones `sync` y `api` de `cli.py`, `docker/`, `docker-compose.yml`, `scripts/`, `.github/`, `artifacts_demo/`, `tests/test_api.py`, `tests/test_contratos.py`, `docs/`, `README.md` |
| Tu rama | `produccion` |
| Lo exclusivo tuyo | Solo tu llave SSH entra al servidor y solo tú tienes el token de Databricks. Tú corres todo en las ventanas ▶. |

Fechas límite:

| Hito | Cuándo | Qué |
| --- | --- | --- |
| H0 | Hoy, antes de clase | Repo base + imagen pública en GHCR + `.env` probado. |
| Clase martes | Hoy | Infraestructura probada (guion de la sección 4). |
| H2 | Jueves 12, 2:00 p. m. | API completa, página, CI/CD, logs simulados en bronce. |
| H3 | Jueves 12, 10:00 p. m. | Simulacro completo en la Mac con artifacts reales (coordinas tú). |
| Clase viernes | Viernes 13 | Despliegue final y evidencias (guion de la sección 7). |

---

## 2. Hoy antes de la clase ⏸ (en este orden)

Lo indispensable para la clase está marcado con ⭐. Si algo no da tiempo, salta a la sección 4.3 (plan B) para la clase.

### 2.1 ⭐ Alias SSH en tu Mac (2 min)

```bash
nano ~/.ssh/config
```

Pega al final:

```
Host gasolina
    HostName 159.65.111.14
    User cc3105
    IdentityFile ~/.ssh/id_ed25519
    ServerAliveInterval 30
```

Guarda con `Ctrl + O`, Enter, y sal con `Ctrl + X`.

### 2.2 ⭐ GitHub (5 min) 🐙

1. Crea el repo `gasolina-mlops`, público (se clona sin llaves y la imagen se descarga sin iniciar sesión; por eso nunca se suben tokens ni datos).
2. Settings → Collaborators → agrega a tus 2 compañeros.
3. Settings → Actions → General → Workflow permissions → "Read and write permissions" → Save.

### 2.3 ⭐ Mándales su instructivo a los compañeros (2 min)

Por WhatsApp: `2_DATOS.md` y `3_MODELOS.md`, más las 5 fotos de `Proyecto/datos/` como documento (no como foto, para que no se pierda la metadata EXIF). Pueden empezar ya con lo que no necesita el repo.

### 2.4 ⭐ Repo base (30–45 min) 💻

Abre Claude Code en la carpeta `Proyecto` y pega:

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

Revisa el resumen que te dé. Lo mínimo que tiene que funcionar: `pytest` pasa y `curl localhost:8000/health` responde. Luego:

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

Ambiente local:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[api,dev]"
```

Avisa en el chat: "Repo listo: https://github.com/TU_USUARIO/gasolina-mlops. Cada quien en su rama".

### 2.5 ⭐ Imagen pública en GHCR (10 min, mientras haces lo siguiente) 🐙

1. Pestaña Actions → espera el workflow `ci` en verde (unos 5 a 8 minutos).
2. Tu perfil → Packages → `gasolina-mlops` → Package settings → Change visibility → Public.
3. Si tienes Docker en la Mac: `docker pull ghcr.io/TU_USUARIO_EN_MINUSCULAS/gasolina-mlops:latest`.

Si el CI falla, copia el log del paso que falló y pégalo en Claude Code con el prompt de errores (sección 9).

### 2.6 ⭐ Databricks: volúmenes y artifacts demo (5 min) 🧱

Si la persona de Datos ya creó los esquemas, solo verifica. Si no, en un notebook:

```sql
%sql
CREATE SCHEMA IF NOT EXISTS workspace.g6_bronce;
CREATE SCHEMA IF NOT EXISTS workspace.g6_plata;
CREATE SCHEMA IF NOT EXISTS workspace.g6_oro;
CREATE VOLUME IF NOT EXISTS workspace.g6_bronce.crudos;
CREATE VOLUME IF NOT EXISTS workspace.g6_oro.artifacts;
```

Luego:

1. Catalog → `g6_oro` → Volumes → `artifacts` → Upload to this volume → sube los 6 JSON de `artifacts_demo/`.
2. Catalog → `g6_bronce` → Volumes → `crudos` → Create directory → `api_logs`.

### 2.7 ⭐ `.env` probado y token nuevo (10 min) 💻

Como el token viejo quedó escrito en el instructivo anterior, genera uno nuevo (foto de perfil → Settings → Developer → Access tokens → Generate new token, nombre `servidor-g6`, 90 días) y revoca el anterior. Borra también el token del archivo `INSTRUCTIVO_PROYECTO_FINAL.md`.

En una nota privada (no en el repo) deja listo:

```
DATABRICKS_HOST=https://URL-DE-TU-WORKSPACE
DATABRICKS_TOKEN=dapi...
GOLD_ARTIFACTS_PATH=/Volumes/workspace/g6_oro/artifacts
BRONZE_LOGS_PATH=/Volumes/workspace/g6_bronce/crudos/api_logs
ARTIFACTS_DIR=/app/artifacts
IMAGEN_DOCKER=ghcr.io/TU_USUARIO_EN_MINUSCULAS/gasolina-mlops:latest
```

Pruébalo en la Mac:

```bash
cd ".../Proyecto/gasolina-mlops"
nano .env            # pega lo de la nota
set -a; source .env; set +a
ARTIFACTS_DIR=./artifacts gasolina-sync descargar
ls artifacts/        # deben estar los 6 JSON demo + manifest.json
```

Si da 401/403, el token está mal copiado.

### 2.8 ⭐ Llave para GitHub Actions y secrets (5 min) 💻 🐙

```bash
ssh-keygen -t ed25519 -f ~/.ssh/gha_deploy -C "github-actions-g6" -N ""
cat ~/.ssh/gha_deploy.pub     # guarda esta línea en tu nota: se agrega al servidor en clase
cat ~/.ssh/gha_deploy         # esto va al secret SSH_PRIVATE_KEY
```

GitHub → Settings → Secrets and variables → Actions → New repository secret:

| Secret | Valor |
| --- | --- |
| `SSH_HOST` | `159.65.111.14` |
| `SSH_USER` | `cc3105` |
| `SSH_PRIVATE_KEY` | Todo el contenido de `~/.ssh/gha_deploy`, incluidas las líneas BEGIN y END |

### 2.9 Checklist antes de entrar a clase

- [ ] Alias `gasolina` en `~/.ssh/config`.
- [ ] Repo público, CI en verde, imagen pública en GHCR.
- [ ] Artifacts demo en `g6_oro/artifacts` y carpeta `crudos/api_logs`.
- [ ] `.env` probado en la Mac; nota privada con `.env` y la línea de `gha_deploy.pub`.
- [ ] Secrets de GitHub creados.
- [ ] Preguntas para el profesor a mano (sección 8).
- [ ] Dos pestañas de Terminal: una para el servidor y otra para la Mac.

---

## 3. Qué vas a correr en el servidor (resumen)

| Comando | Para qué |
| --- | --- |
| `bash scripts/servidor_check.sh` | Inventario: Docker, RAM, puerto. Guarda `~/servidor_check.txt`. |
| `bash scripts/deploy.sh` | `git pull` → sync de artifacts → imagen → API arriba → espera `/health`. Detecta solo si usar Docker o venv. |
| `bash scripts/fin_de_clase.sh` | Sube los logs a bronce y muestra el estado. Córrelo siempre antes de que apaguen el servidor. |
| `docker compose run --rm --no-deps api gasolina-sync descargar` | Trae artifacts nuevos sin reiniciar la API. |

---

## 4. Hoy en la clase ▶ (1:30 h)

### 4.1 Guion

| Minuto | Qué hacer | Cómo sabes que quedó |
| --- | --- | --- |
| 0–5 | Preguntas al profesor (sección 8). | Respuestas anotadas. |
| 5–10 | Clonar el repo en el servidor. | `~/apps/gasolina-mlops` existe. |
| 10–15 | `bash scripts/servidor_check.sh` | Sabes si hay Docker, RAM y puerto libre. |
| 15–20 | Crear `.env` en el servidor. | 6 líneas, `chmod 600`. |
| 20–35 | `bash scripts/deploy.sh` | Termina con `/health` en `ok`. |
| 35–45 | Probar desde la Mac. | `/health` responde por IP y la página abre. |
| 45–55 | Llave de GitHub Actions + workflow `deploy` manual. | Workflow en verde. |
| 55–65 | 2 fotos desde la Mac + `fin_de_clase.sh`. | `.jsonl` en `crudos/api_logs/`. |
| 65–75 | Cron + probar reinicio. | `crontab -l` y `/health` responde tras reiniciar. |
| 75–85 | Capturas y copiar `servidor_check.txt` a la Mac. | `evidencias/clase_martes/`. |
| 85–90 | `fin_de_clase.sh` y lista de pendientes. | Mensaje en el chat. |

### 4.2 Comandos

```bash
# 🌊 servidor
ssh gasolina
mkdir -p ~/apps && cd ~/apps
git clone https://github.com/TU_USUARIO/gasolina-mlops.git
cd gasolina-mlops
bash scripts/servidor_check.sh
nano .env            # pega tu nota privada
chmod 600 .env
bash scripts/deploy.sh
```

Cómo interpretar `servidor_check`:

| Resultado | Significa | Qué hacer |
| --- | --- | --- |
| `docker ps` muestra una tabla (aunque vacía) | Puedes usar Docker. | `deploy.sh` lo detecta solo. |
| `docker ps` dice `permission denied` | Tu usuario no está en el grupo `docker`. | Pídele al profesor: "¿Puede agregar al usuario cc3105 al grupo docker?" (después sal y vuelve a entrar). Mientras tanto, `deploy.sh` usa venv. |
| Menos de 1.5 GB de RAM | Servidor chico. | RapidOCR cabe. No uses EasyOCR en producción. |
| `SIN SUDO` | No puedes instalar paquetes del sistema. | Normal. |
| Puerto 8000 ocupado | Otro equipo lo usa. | Cambia `8000:8000` por `8010:8000` en `docker-compose.yml` (commit desde la Mac, `git pull` en el servidor) y usa ese puerto. |

```bash
# 💻 Mac (otra pestaña), desde la carpeta Proyecto
curl http://159.65.111.14:8000/health
curl -F "foto=@datos/IMG_8271.jpg" http://159.65.111.14:8000/extraer
curl -F "foto=@datos/IMG_8286.jpg" http://159.65.111.14:8000/extraer
open http://159.65.111.14:8000
```

Hoy los precios salen en `null` (modo stub): es lo esperado. Si desde el servidor funciona (`curl localhost:8000/health`) pero desde la Mac no, el puerto está bloqueado: pídele al profesor que abra el 8000 y, mientras tanto, usa `ssh -L 8000:localhost:8000 gasolina` y `http://localhost:8000`.

```bash
# 🌊 llave de GitHub Actions (con permiso del profesor)
echo "PEGA-AQUÍ-LA-LÍNEA-DE-gha_deploy.pub" >> ~/.ssh/authorized_keys
```

Luego 🐙 Actions → `deploy` → Run workflow (rama `main`).

```bash
# 🌊 logs a bronce
bash scripts/fin_de_clase.sh

# 🌊 cron (una sola línea)
crontab -e
0 * * * * cd ~/apps/gasolina-mlops && docker compose run --rm --no-deps api gasolina-sync subir-logs >> logs/sync.log 2>&1
# modo venv: 0 * * * * cd ~/apps/gasolina-mlops && set -a && . ./.env && set +a && .venv/bin/gasolina-sync subir-logs >> logs/sync.log 2>&1

# 🌊 probar que se levanta sola
docker compose restart && sleep 20 && curl -s localhost:8000/health
```

```bash
# 💻 evidencias
mkdir -p "../evidencias/clase_martes"
scp gasolina:~/servidor_check.txt "../evidencias/clase_martes/"
```

Si el repo fuera privado: en el servidor `ssh-keygen -t ed25519 -f ~/.ssh/github_deploy -C "deploy-g6"`, `cat ~/.ssh/github_deploy.pub`, agrégala en GitHub → Settings → Deploy keys (solo lectura) y clona con `GIT_SSH_COMMAND="ssh -i ~/.ssh/github_deploy" git clone git@github.com:TU_USUARIO/gasolina-mlops.git`.

### 4.3 Plan B si el repo base no quedó listo

Resuelve todas las incógnitas del servidor:

```bash
# 🌊 inventario manual
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

# 🌊 Docker
docker run --rm hello-world

# 🌊 puerto (luego, en la Mac: curl -I http://159.65.111.14:8000 ; después Ctrl + C aquí)
python3 -m http.server 8000

# 🌊 conexión con Databricks (200 = ok; el token no queda en el historial)
read -s DATABRICKS_TOKEN; export DATABRICKS_TOKEN
curl -s -o /dev/null -w "%{http_code}\n" -H "Authorization: Bearer $DATABRICKS_TOKEN" \
  https://URL-DE-TU-WORKSPACE/api/2.1/unity-catalog/catalogs
```

Y agrega la llave de GitHub Actions. Con eso, el viernes solo falta desplegar.

Plan B de artifacts (si el token no funciona desde el servidor): descárgalos en la Mac con `gasolina-sync descargar` y cópialos con `scp artifacts/* gasolina:~/apps/gasolina-mlops/artifacts/`. Documéntenlo en el reporte (en una empresa sería un service principal).

---

## 5. Martes noche a jueves ⏸: desarrollo (hito H2, jueves 2:00 p. m.)

Trabaja en la rama `produccion`. Todo se prueba con los artifacts demo; cuando lleguen los reales, solo corres `gasolina-sync descargar`.

### 5.1 ⭐ API completa

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

Prueba local:

```bash
gasolina-api
# en otra terminal:
curl http://localhost:8000/health
curl -F "foto=@../datos/IMG_8271.jpg" http://localhost:8000/extraer
open http://localhost:8000/docs
```

### 5.2 ⭐ Endpoints de monitoreo

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

### 5.3 ⭐ Página web

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

### 5.4 ⭐ CI/CD

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

### 5.5 ⭐ Tráfico simulado para Datos (antes del jueves 2:00 p. m.)

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

### 5.6 Integración

Cada vez que termines una parte: PR de `produccion` a `main`, CI en verde, merge. Cuando Modelos haga merge del OCR real, corre otra vez `pytest` y prueba `/extraer`: ya deben salir precios. Si algo del contrato no cuadra (sección 4 del general), avísalo de inmediato.

Checklist H2:

- [ ] `/health`, `/extraer`, `/pronostico`, `/historico`, `/metricas`, `/monitoreo/produccion`, `/monitoreo/modelo` responden en local.
- [ ] La página tiene las 4 pestañas y no se rompe si falta un artifact.
- [ ] CI en verde y la imagen nueva publicada.
- [ ] Logs simulados en bronce.

---

## 6. Jueves 10:00 p. m. ⏸: simulacro completo (hito H3, coordinas tú)

En llamada con los otros dos. Lo que corre aquí es exactamente lo que va a correr en el servidor.

1. Todos los PR en `main` y el CI en verde.
2. Datos confirma que `g6_pipeline_semanal` corrió en verde.
3. Revisa en Databricks que los 7 artifacts reales estén en `g6_oro/artifacts` (ninguno con `"origen": "demo"`).
4. En la Mac:

```bash
git checkout main && git pull
set -a; source .env; set +a
docker compose pull
docker compose run --rm --no-deps api gasolina-sync descargar
docker compose up -d
curl -s localhost:8000/health | python3 -m json.tool        # origen: databricks, modo: real
python scripts/generar_trafico.py --url http://localhost:8000 --carpeta ../datos --repeticiones 3
docker compose run --rm --no-deps api gasolina-sync subir-logs
```

5. Datos corre `g6_monitoreo_diario`; tú corres otra vez `gasolina-sync descargar` y revisas la pestaña "Monitoreo".
6. Revisen juntos las 4 pestañas en `http://localhost:8000`.
7. Graba con QuickTime un video de respaldo de la demo local.
8. `main` se congela: después de esto, cualquier cambio necesita el visto bueno de los 3.

Si no tienes Docker en la Mac: mismo simulacro con `ARTIFACTS_DIR=./artifacts gasolina-sync descargar` y `ARTIFACTS_DIR=./artifacts gasolina-api`.

---

## 7. Viernes en la clase ▶ (1:30 h)

| Minuto | Quién | Qué hacer | Evidencia |
| --- | --- | --- | --- |
| 0–3 | Tú | Confirmar con el profesor si el servidor estará encendido el día de la presentación. | Respuesta anotada. |
| 3–15 | Tú | `ssh gasolina` → `cd ~/apps/gasolina-mlops && bash scripts/deploy.sh` (o el workflow `deploy` desde GitHub). | `/health` con `origen: databricks` y `modo: real`. |
| 15–25 | Modelos | `generar_trafico.py` contra `http://159.65.111.14:8000` y fotos nuevas desde la página. | Tabla en la Terminal. |
| 15–30 | Tú y Datos | Capturas: 4 pestañas, `/docs`, `/health`, `docker compose ps`, workflow `deploy`. | `evidencias/clase_viernes/` |
| 30–45 | Todos | Video de la demo en vivo (guion abajo). | Video `.mov`. |
| 45–55 | Tú | `bash scripts/fin_de_clase.sh` | `.jsonl` del día en bronce. |
| 55–70 | Datos | Correr `g6_monitoreo_diario` y refrescar el dashboard. | Capturas con `entorno = servidor`. |
| 70–80 | Tú | `docker compose run --rm --no-deps api gasolina-sync descargar` | "Salud del modelo" actualizada en vivo. |
| 80–90 | Tú | `fin_de_clase.sh` final; `scp -r gasolina:~/apps/gasolina-mlops/logs ../evidencias/clase_viernes/`. Deja la API corriendo. | Logs en la Mac. |

Si el despliegue falla y no se arregla en 10 minutos: demo con la misma imagen en la Mac y se documenta.

Guion del video (2–3 min): URL y `/health` → "Leer foto" con una foto conocida y una nueva (ruta A, ruta B, fusión, validaciones) → "Pronóstico" → "Monitoreo" → corte a Databricks (capas, MLflow Compare, champion, job, dashboard).

---

## 8. Preguntas para el profesor (martes, al inicio)

1. ¿Va a encender el servidor el viernes? ¿Y el día de la presentación final? ¿A qué hora?
2. ¿El usuario `cc3105` puede usar Docker? ¿Está abierto el puerto 8000 (o cuál podemos usar)?
3. ¿Podemos agregar una llave SSH para GitHub Actions al usuario `cc3105`?
4. ¿Podemos usar un token personal de Databricks desde el droplet?
5. ¿Formato de entrega (reporte, repo, demo, presentación) y fecha?
6. ¿Hay external location de S3 para el equipo?
7. ¿Más imágenes o usamos las 5 + las nuestras?
8. Si el servidor no está encendido en la presentación, ¿acepta la demo grabada el viernes + la misma imagen en local?

---

## 9. Problemas comunes de tu parte

| Problema | Solución |
| --- | --- |
| `ssh: connect to host ... timed out` | El servidor está apagado. Normal fuera de clase. |
| `docker compose pull` dice `denied` | La imagen en GHCR es privada: cámbiala a pública. `deploy.sh` la construye mientras tanto. |
| `exec format error` | Imagen construida en tu Mac (arm64). Usa solo la de GitHub Actions. |
| `gasolina-sync` 401/403 | Token vencido o mal copiado: genera otro y actualiza `.env` en la Mac y en el servidor. |
| `/health` dice `origen: demo` | Faltan artifacts reales en `g6_oro/artifacts` o no corriste `descargar`. |
| La API no responde desde la Mac | Puerto cerrado: pedir abrirlo o túnel `ssh -L 8000:localhost:8000 gasolina`. |
| Algo se rompió en el servidor | Nunca editar a mano ahí: arreglar en el repo, merge a `main` y `deploy.sh`. |

Para cualquier error:

```
PROMPT PARA CLAUDE CODE
Estoy en el paso [X.Y] del instructivo [general / de mi rol]. Corrí: [comando]. Me salió:
[error completo]. Estoy en [mi Mac / el servidor / Databricks]. Explícame qué significa y
dame el arreglo paso a paso.
```
