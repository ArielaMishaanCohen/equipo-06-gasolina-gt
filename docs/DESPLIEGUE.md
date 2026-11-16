# Despliegue de la API

La entrega está integrada en `main`. El servidor ya tiene el `.env` configurado
(puerto 8000, SQL warehouse); para actualizar basta con traer `main` y volver a desplegar.

## Actualizar el proyecto

Utiliza la llave y el usuario asignados al equipo. Confirma que el servidor esté encendido.

```bash
ssh -i RUTA_DE_TU_LLAVE USUARIO_DEL_EQUIPO@159.65.111.14
cd ~/apps/gasolina-mlops
git switch main
git pull --ff-only
```

## Configurar el archivo privado .env

Solo hace falta en una instalación nueva. Las tablas del workspace son gestionadas y la
API las lee por el SQL warehouse (aprobado por el catedrático el 13 de noviembre).

```dotenv
PUERTO=8000
DATABRICKS_HOST=https://dbc-f51e9943-f137.cloud.databricks.com
DATABRICKS_TOKEN=TOKEN_DE_LA_CUENTA_AUTORIZADA
DATABRICKS_WAREHOUSE_ID=48a52c351a0af482
BRONZE_LOGS_PATH=/Volumes/workspace/equipo6_bronze/crudos/api_logs
ENTORNO=servidor
```

La cuenta para la API necesita acceso al warehouse y lectura de las tablas de
`workspace.equipo_06_gold`. Sus credenciales deben tener permisos de lectura sobre Oro.
Los tokens y las llaves se configuran en el servidor y se excluyen de Git.

## Desplegar y comprobar

```bash
chmod 600 .env
bash scripts/deploy.sh --modo venv
curl --fail --max-time 30 http://localhost:8000/health
BASE_URL=http://localhost:8000 bash tests/consultas_api.sh
```

Si falla el despliegue, revisa `logs/api.log` y el acceso del token al warehouse.
Después comprueba desde otra computadora.

```bash
curl --fail --max-time 30 http://159.65.111.14:8000/health
BASE_URL=http://159.65.111.14:8000 bash tests/consultas_api.sh
```

La respuesta de health debe indicar `fuente_oro=databricks` para esta configuración.
Las predicciones deben corresponder al histórico disponible, con objetivo `2026-11-10`.
Guarda las salidas y una captura del servicio público. Actualiza el estado de la API
en el informe y la presentación después de esa comprobación.

## Alternativa de tablas externas

Otra ruta S3 puede utilizarse si tiene escritura autorizada y una external location
configurada. Cambiar de subdirectorio dentro de una ubicación de solo lectura conserva
la restricción. El almacenamiento gestionado de Unity Catalog tampoco puede reutilizarse
como ruta de una tabla externa.

La alternativa implementada por SQL funciona con las tablas actuales y fue aprobada
por el catedrático. Si en el futuro se exigiera S3 directo, se necesitaría una ruta
autorizada y las credenciales de lectura correspondientes para la API.

Referencias oficiales sobre las restricciones de almacenamiento.

- https://docs.databricks.com/aws/en/connect/unity-catalog/cloud-storage/manage-external-locations
- https://docs.databricks.com/aws/en/volumes/paths

## Rotar el token de Databricks

1. En Databricks: foto de perfil → Settings → Developer → Access tokens → Generate new token
   (nombre `servidor-g6-AAAAMMDD`, 90 días). Copiarlo una sola vez.
2. En el servidor, reemplazar la línea `DATABRICKS_TOKEN=` del `.env` con un editor
   (`nano ~/apps/gasolina-mlops/.env`), sin pegar el token en la terminal ni en el chat.
3. Volver a desplegar y comprobar que `/health` siga respondiendo `fuente_oro=databricks`:
   `bash scripts/deploy.sh --modo venv && curl -s http://localhost:8000/health`.
4. Hacer lo mismo en el `.env` local si se usa.
5. Solo después de comprobarlo, revocar el token anterior en Access tokens.
