"""Sincronización con Databricks (dueña: Producción).

  subir-logs : LOGS_DIR/*.jsonl -> BRONZE_LOGS_PATH (registro en LOGS_DIR/.subidos.json)

Credenciales: DATABRICKS_HOST y DATABRICKS_TOKEN (variables de entorno o .env).
El registro de subidos vive dentro de logs/, que en Docker es un volumen; así funciona igual
dentro y fuera del contenedor.

En Databricks, los logs quedan como <ENTORNO>_predicciones_YYYYMMDD.jsonl (ej.
servidor_predicciones_20261113.jsonl) para que los simulados de la Mac ("local") y los del
droplet ("servidor") no se pisen aunque sean del mismo día.
"""

from __future__ import annotations

import io
import json
import socket
import sys
from datetime import datetime, timezone
from pathlib import Path

from gasolina.config import Ajustes, ajustes

REGISTRO_SUBIDOS = ".subidos.json"


class ErrorSync(RuntimeError):
    """Error con un mensaje listo para mostrarle a una persona."""


# --------------------------------------------------------------------------- cliente


def _cliente(aj: Ajustes):
    if not aj.databricks_host or not aj.databricks_token:
        raise ErrorSync(
            "Faltan DATABRICKS_HOST y/o DATABRICKS_TOKEN. Revisa tu .env "
            "(o en la Mac: set -a; source .env; set +a)."
        )
    try:
        from databricks.sdk import WorkspaceClient
        from databricks.sdk.core import Config
    except ImportError as e:  # pragma: no cover
        raise ErrorSync('Falta databricks-sdk. Instala con: pip install -e ".[api]"') from e
    try:
        cfg = Config(
            host=aj.databricks_host,
            token=aj.databricks_token,
            auth_type="pat",
            retry_timeout_seconds=45,  # sin red: falla en ~45 s en lugar de 5 min
            http_timeout_seconds=30,
        )
    except Exception as e:
        raise _traducir_error(e, "Configuración de Databricks inválida") from e
    return WorkspaceClient(config=cfg)


def _traducir_error(e: Exception, contexto: str) -> ErrorSync:
    """Convierte errores del SDK / red en mensajes claros en español."""
    nombre = type(e).__name__
    texto = str(e)
    codigo = getattr(e, "status_code", None) or getattr(getattr(e, "response", None),
                                                         "status_code", None)
    bajo = texto.lower()
    if nombre in ("Unauthenticated",) or codigo == 401 or "401" in texto or (
        "invalid access token" in bajo or "credential" in bajo and "invalid" in bajo
    ):
        return ErrorSync(
            f"{contexto}: token inválido o vencido (401). Genera un token nuevo en Databricks "
            "(Settings -> Developer -> Access tokens) y actualiza DATABRICKS_TOKEN en .env."
        )
    if nombre in ("PermissionDenied",) or codigo == 403 or "403" in texto:
        return ErrorSync(
            f"{contexto}: sin permiso (403). El token es válido pero tu usuario no tiene acceso "
            "a esa ruta. Revisa los permisos del volumen (READ/WRITE VOLUME)."
        )
    if nombre in ("NotFound", "ResourceDoesNotExist") or codigo == 404:
        return ErrorSync(
            f"{contexto}: la ruta no existe (404). Revisa que el volumen exista en Databricks "
            "(notebooks/00_setup.sql) y la ruta en .env."
        )
    red = (
        isinstance(e, (ConnectionError, TimeoutError, socket.gaierror))
        or "connection" in bajo
        or "timed out" in bajo
        or "name or service not known" in bajo
        or "nodename nor servname" in bajo
        or "max retries" in bajo
        or "failed to resolve" in bajo
    )
    if red:
        return ErrorSync(
            f"{contexto}: no hay conexión con Databricks ({nombre}). ¿Hay internet? "
            "¿DATABRICKS_HOST es correcto (https://...cloud.databricks.com)?"
        )
    return ErrorSync(f"{contexto}: error inesperado {nombre}: {texto[:300]}")


# --------------------------------------------------------------------------- subir-logs


def _leer_registro(ruta: Path) -> dict:
    if ruta.is_file():
        try:
            return json.loads(ruta.read_text())
        except json.JSONDecodeError:
            print(f"AVISO: {ruta} estaba corrupto; se vuelve a empezar el registro.")
    return {}


def subir_logs(aj: Ajustes | None = None) -> list[str]:
    """Sube los logs/*.jsonl nuevos o que cambiaron de tamaño a BRONZE_LOGS_PATH."""
    aj = aj or ajustes()
    logs = aj.logs_dir
    if not logs.is_dir():
        print(f"No existe {logs.resolve()}: no hay logs que subir.")
        return []
    ruta_registro = logs / REGISTRO_SUBIDOS
    registro = _leer_registro(ruta_registro)

    pendientes = []
    for archivo in sorted(logs.glob("*.jsonl")):
        tam = archivo.stat().st_size
        if tam == 0:
            continue
        previo = registro.get(archivo.name)
        # Nuevo, o cambió de tamaño (típicamente el archivo del día actual, que sigue creciendo).
        if previo is None or previo.get("bytes") != tam:
            pendientes.append((archivo, tam))

    if not pendientes:
        print("No hay logs nuevos que subir.")
        return []

    w = _cliente(aj)
    destino_dir = aj.bronze_logs_path
    try:
        w.files.create_directory(destino_dir)
    except Exception as e:
        raise _traducir_error(e, f"No se pudo preparar {destino_dir}") from e

    subidos = []
    for archivo, tam in pendientes:
        remoto = f"{destino_dir}/{aj.entorno}_{archivo.name}"
        try:
            datos = archivo.read_bytes()[:tam]  # solo hasta el tamaño medido
            w.files.upload(remoto, io.BytesIO(datos), overwrite=True)
        except Exception as e:
            # Guardar lo que sí se subió antes de fallar.
            ruta_registro.write_text(json.dumps(registro, indent=2))
            raise _traducir_error(e, f"No se pudo subir {archivo.name}") from e
        registro[archivo.name] = {
            "bytes": tam,
            "remoto": remoto,
            "fecha_subida": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        subidos.append(remoto)
        print(f"  ✓ {archivo.name} -> {remoto} ({tam} bytes)")

    ruta_registro.write_text(json.dumps(registro, indent=2))
    print(f"Listo: {len(subidos)} archivo(s) subido(s).")
    return subidos


def main(accion: str) -> int:
    try:
        if accion == "subir-logs":
            subir_logs()
        else:
            print(f"Acción desconocida: {accion}", file=sys.stderr)
            return 2
    except ErrorSync as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    return 0
