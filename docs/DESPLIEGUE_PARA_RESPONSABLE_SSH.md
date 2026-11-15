# Despliegue para la responsable de SSH

Los cambios están preparados en la rama `modelos-completar`. El integrante debe hacer
commit y push antes de ejecutar esta guía en el servidor.

## Actualizar el proyecto

Utiliza la llave y el usuario asignados al equipo. Confirma que el servidor esté encendido.

```bash
ssh -i RUTA_DE_TU_LLAVE USUARIO_DEL_EQUIPO@159.65.111.14
cd ~/apps/gasolina-mlops
git fetch origin
git switch modelos-completar
git pull --ff-only
```

Si el equipo ya integró la entrega a `main`, utiliza esa rama.

## Configurar el archivo privado .env

Las tablas del workspace son gestionadas. La alternativa de lectura ya implementada usa
el SQL warehouse. Configura estos valores directamente en el servidor.

```dotenv
PUERTO=8006
DATABRICKS_HOST=https://dbc-f51e9943-f137.cloud.databricks.com
DATABRICKS_TOKEN=TOKEN_DE_LA_CUENTA_AUTORIZADA
DATABRICKS_WAREHOUSE_ID=48a52c351a0af482
BRONZE_LOGS_PATH=/Volumes/workspace/equipo6_bronze/crudos/api_logs
ENTORNO=servidor
```

La cuenta para la API necesita acceso al warehouse y lectura de las tablas de
`workspace.equipo6_gold`. Sus credenciales deben tener permisos de lectura sobre Oro.
Los tokens y las llaves se configuran en el servidor y se excluyen de Git.

## Desplegar y comprobar

```bash
chmod 600 .env
bash scripts/deploy.sh --modo venv
curl --fail --max-time 30 http://localhost:8006/health
BASE_URL=http://localhost:8006 bash tests/consultas_api.sh
```

Si falla el despliegue, revisa `logs/api.log` y el acceso del token al warehouse.
Después comprueba desde otra computadora.

```bash
curl --fail --max-time 30 http://159.65.111.14:8006/health
BASE_URL=http://159.65.111.14:8006 bash tests/consultas_api.sh
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

La alternativa implementada por SQL funciona con las tablas actuales. El equipo debe
confirmar su aceptación con el catedrático. Si se exige S3 directo, se necesita una ruta
autorizada y las credenciales de lectura correspondientes para la API.

Referencias oficiales sobre las restricciones de almacenamiento.

- https://docs.databricks.com/aws/en/connect/unity-catalog/cloud-storage/manage-external-locations
- https://docs.databricks.com/aws/en/volumes/paths
