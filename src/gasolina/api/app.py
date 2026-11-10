"""API de producción (dueña: Producción). Versión mínima pero real.

Endpoints:
  GET  /                      página web (static/index.html)
  GET  /health                estado, versiones, origen de artifacts, modo de extracción
  POST /extraer               foto (multipart, campo "foto") -> contrato 4.1; ?debug=true
  GET  /pronostico            predicciones.json
  GET  /historico             historico.json + predicciones
  GET  /metricas              contadores en memoria desde que arrancó la API
  GET  /monitoreo/produccion  resumen calculado desde logs/*.jsonl
  GET  /monitoreo/modelo      monitoreo.json (job de Databricks)

Artifacts: se leen de ARTIFACTS_DIR; si un archivo no está ahí, se usa el de artifacts_demo/.
Cada JSON se vuelve a leer cuando cambia su fecha de modificación, así que un
`gasolina-sync descargar` los actualiza sin reiniciar la API.
"""

from __future__ import annotations

import inspect
import json
import logging
import tempfile
import threading
import time
import uuid
from collections import Counter, deque
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, JSONResponse

from gasolina import __version__
from gasolina import extraccion as _extraccion
from gasolina.config import ajustes, cargar_config

log = logging.getLogger("gasolina.api")

NOMBRES_ARTIFACTS = (
    "ocr_config.json",
    "reglas.json",
    "forecast_meta.json",
    "predicciones.json",
    "historico.json",
    "monitoreo.json",
)
STATIC = Path(__file__).parent / "static"


def _tz() -> timezone:
    horas = cargar_config()["api"].get("zona_horaria_utc", -6)
    return timezone(timedelta(hours=horas))


def _ahora() -> datetime:
    return datetime.now(_tz())


# ------------------------------------------------------------------ artifacts


class Artifacts:
    """Lee los JSON de artifacts con caché por fecha de modificación y fallback a demo."""

    def __init__(self, directorio: Path, directorio_demo: Path):
        self.directorio = directorio
        self.directorio_demo = directorio_demo
        self._cache: dict[str, tuple[Path, float, dict]] = {}
        self._lock = threading.Lock()

    def _resolver(self, nombre: str) -> tuple[Path | None, str | None]:
        real = self.directorio / nombre
        if real.is_file():
            return real, "databricks"
        demo = self.directorio_demo / nombre
        if demo.is_file():
            return demo, "demo"
        return None, None

    def get(self, nombre: str) -> dict | None:
        ruta, _ = self._resolver(nombre)
        if ruta is None:
            return None
        try:
            mtime = ruta.stat().st_mtime
        except OSError:
            return None
        with self._lock:
            previo = self._cache.get(nombre)
            if previo and previo[0] == ruta and previo[1] == mtime:
                return previo[2]
            try:
                datos = json.loads(ruta.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as e:
                log.warning("No se pudo leer %s: %s", ruta, e)
                return previo[2] if previo else None
            self._cache[nombre] = (ruta, mtime, datos)
            log.info("Artifact cargado: %s", ruta)
            return datos

    def estado(self) -> dict:
        detalle = {}
        fuentes = []
        for nombre in NOMBRES_ARTIFACTS:
            ruta, fuente = self._resolver(nombre)
            datos = self.get(nombre) if ruta else None
            fuentes.append(fuente)
            detalle[nombre] = {
                "cargado": datos is not None,
                "fuente": fuente,  # databricks = ARTIFACTS_DIR (sincronizado), demo = respaldo
                "origen_contenido": (datos or {}).get("origen"),
                "version": (datos or {}).get("version"),
                "fecha": (datos or {}).get("fecha"),
                "ruta": str(ruta) if ruta else None,
            }
        if all(f == "databricks" for f in fuentes):
            origen = "databricks"
        elif all(f in ("demo", None) for f in fuentes):
            origen = "demo"
        else:
            origen = "mixto"
        return {"origen": origen, "detalle": detalle}


# ------------------------------------------------------------------ métricas en memoria


class Metricas:
    def __init__(self, maximo: int = 10_000):
        self._lock = threading.Lock()
        self.total = 0
        self.errores = 0
        self.inicio = _ahora()
        self._latencias: deque[float] = deque(maxlen=maximo)
        self._scores: deque[float] = deque(maxlen=maximo)

    def registrar(self, latencia_ms: float, score: float | None) -> None:
        with self._lock:
            self.total += 1
            self._latencias.append(latencia_ms)
            if score is not None:
                self._scores.append(score)

    def error(self) -> None:
        with self._lock:
            self.errores += 1

    def resumen(self, umbral: float) -> dict:
        with self._lock:
            lat = list(self._latencias)
            sc = list(self._scores)
            total, errores = self.total, self.errores
        return {
            "desde": self.inicio.isoformat(timespec="seconds"),
            "total": total,
            "errores": errores,
            "umbral_score": umbral,
            "pct_score_alto": round(100 * sum(s >= umbral for s in sc) / len(sc), 1)
            if sc
            else None,
            "latencia_ms_p50": _percentil(lat, 50),
            "latencia_ms_p95": _percentil(lat, 95),
        }


def _percentil(valores: list[float], p: float) -> float | None:
    if not valores:
        return None
    v = sorted(valores)
    k = (len(v) - 1) * p / 100
    i = int(k)
    j = min(i + 1, len(v) - 1)
    return round(v[i] + (v[j] - v[i]) * (k - i), 1)


# ------------------------------------------------------------------ logs (contrato 4.3)


def _linea_log(res: dict, latencia_ms: int, origen_artifacts: str, entorno: str) -> dict:
    meta = res.get("metadata") or {}
    fuentes = res.get("fuentes") or {}
    return {
        "id": str(uuid.uuid4()),
        "timestamp": _ahora().isoformat(timespec="seconds"),
        "sha256": meta.get("sha256"),
        "archivo": res.get("archivo"),
        "fecha_foto": meta.get("fecha_hora"),
        "lat": meta.get("lat"),
        "lon": meta.get("lon"),
        "precios": res.get("precios"),
        "fuentes": fuentes,
        "precio_a": (res.get("ruta_a") or {}).get("precio_a"),
        "combustible_despachado": res.get("combustible_despachado"),
        "coincide_a_b": any(f == "ambas" for f in fuentes.values()),
        "score_confianza": res.get("score_confianza"),
        "validaciones_fallidas": [
            v.get("nombre") for v in res.get("validaciones") or [] if v.get("estado") == "falla"
        ],
        "latencia_ms": latencia_ms,
        "modo": res.get("modo"),
        "version_modelo": res.get("version_modelo"),
        "origen_artifacts": origen_artifacts,
        "entorno": entorno,
    }


def _escribir_log(logs_dir: Path, linea: dict) -> None:
    try:
        logs_dir.mkdir(parents=True, exist_ok=True)
        archivo = logs_dir / f"predicciones_{_ahora():%Y%m%d}.jsonl"
        with open(archivo, "a", encoding="utf-8") as f:
            f.write(json.dumps(linea, ensure_ascii=False) + "\n")
    except OSError as e:  # nunca tumbar /extraer por un problema de disco/permisos
        log.error("No se pudo escribir el log en %s: %s", logs_dir, e)


def _leer_logs(logs_dir: Path, dias: int = 30) -> list[dict]:
    if not logs_dir.is_dir():
        return []
    limite = (_ahora() - timedelta(days=dias)).strftime("%Y%m%d")
    filas = []
    for archivo in sorted(logs_dir.glob("predicciones_*.jsonl")):
        if archivo.stem.split("_")[-1] < limite:
            continue
        for linea in archivo.read_text(encoding="utf-8").splitlines():
            try:
                filas.append(json.loads(linea))
            except json.JSONDecodeError:
                continue
    return filas


# ------------------------------------------------------------------ app


def _es_imagen(ruta: Path) -> bool:
    try:
        from PIL import Image

        try:
            import pillow_heif

            pillow_heif.register_heif_opener()
        except ImportError:  # pragma: no cover
            pass
        with Image.open(ruta) as im:
            im.verify()
        return True
    except Exception:
        return False


def _kwargs_aceptados(func, kwargs: dict) -> dict:
    """Pasa solo los parámetros que extraer_precios acepta (por si Modelos cambia la firma)."""
    params = inspect.signature(func).parameters
    if any(p.kind == p.VAR_KEYWORD for p in params.values()):
        return kwargs
    return {k: v for k, v in kwargs.items() if k in params}


def crear_app() -> FastAPI:
    aj = ajustes()
    cfg = cargar_config()
    artifacts = Artifacts(aj.artifacts_dir, aj.artifacts_demo_dir)
    metricas = Metricas()
    max_bytes = int(cfg["api"]["max_mb"]) * 1024 * 1024
    extensiones = {e.lower() for e in cfg["api"]["extensiones"]}

    app = FastAPI(
        title="Gasolina MLOps — Grupo 6",
        version=__version__,
        description="Lectura de precios de gasolina desde fotos + pronóstico.",
    )
    app.state.artifacts = artifacts
    app.state.metricas = metricas
    app.state.ajustes = aj

    def _umbral() -> float:
        ocr = artifacts.get("ocr_config.json") or {}
        return float(ocr.get("umbral_score") or cfg["extraccion"]["umbral_score"])

    estado_inicial = artifacts.estado()
    log.info(
        "API %s | artifacts: %s (ARTIFACTS_DIR=%s, demo=%s) | logs: %s | entorno: %s",
        __version__, estado_inicial["origen"], aj.artifacts_dir, aj.artifacts_demo_dir,
        aj.logs_dir, aj.entorno,
    )
    if estado_inicial["origen"] != "databricks":
        log.warning("Usando artifacts_demo para lo que falte en %s", aj.artifacts_dir)

    @app.get("/", include_in_schema=False)
    def inicio():
        return FileResponse(STATIC / "index.html", media_type="text/html")

    @app.get("/health")
    def health():
        est = artifacts.estado()
        return {
            "status": "ok",
            "version": __version__,
            "origen_artifacts": est["origen"],
            "artifacts": est["detalle"],
            "modo_extraccion": getattr(_extraccion, "MODO_EXTRACCION", "stub"),
            "entorno": aj.entorno,
            "hora_servidor": _ahora().isoformat(timespec="seconds"),
            "peticiones_desde_inicio": metricas.total,
        }

    @app.post("/extraer")
    def extraer(foto: UploadFile = File(...), debug: bool = Query(False)):
        t0 = time.perf_counter()
        nombre = Path(foto.filename or "foto").name
        sufijo = Path(nombre).suffix.lower()
        tipo = (foto.content_type or "").lower()
        if sufijo not in extensiones and not tipo.startswith("image/"):
            raise HTTPException(400, f"'{nombre}' no es una imagen (JPG, PNG o HEIC).")

        datos = foto.file.read(max_bytes + 1)
        if len(datos) > max_bytes:
            raise HTTPException(413, f"La foto pesa más de {cfg['api']['max_mb']} MB.")
        if not datos:
            raise HTTPException(400, "El archivo está vacío.")

        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / f"subida{sufijo if sufijo in extensiones else '.jpg'}"
            ruta.write_bytes(datos)
            if not _es_imagen(ruta):
                raise HTTPException(400, f"'{nombre}' no es una imagen válida (JPG, PNG o HEIC).")

            ocr_cfg = artifacts.get("ocr_config.json") or {}
            reglas = artifacts.get("reglas.json") or {}
            kwargs = {
                "motor": ocr_cfg.get("motor") or cfg["extraccion"]["motor"],
                "preproc": ocr_cfg.get("preproc") or cfg["extraccion"]["preproc"],
                "estrategia": ocr_cfg.get("estrategia") or cfg["extraccion"]["estrategia"],
                "segunda_pasada": bool(ocr_cfg.get("segunda_pasada", False)),
                "referencia": reglas.get("referencia_mem"),
            }
            try:
                res = _extraccion.extraer_precios(
                    ruta, **_kwargs_aceptados(_extraccion.extraer_precios, kwargs)
                )
            except Exception as e:
                metricas.error()
                log.exception("Error en extraer_precios")
                return JSONResponse(
                    status_code=500,
                    content={"error": "Falló la extracción", "detalle": f"{type(e).__name__}: {e}"},
                )

        # El archivo temporal tiene otro nombre: devolver el nombre original.
        res["archivo"] = nombre
        if isinstance(res.get("metadata"), dict):
            res["metadata"]["archivo"] = nombre
        if not debug:
            res["detecciones_crudas"] = []

        latencia_ms = round((time.perf_counter() - t0) * 1000)
        metricas.registrar(latencia_ms, res.get("score_confianza"))
        _escribir_log(
            aj.logs_dir,
            _linea_log(res, latencia_ms, artifacts.estado()["origen"], aj.entorno),
        )
        return res

    @app.get("/pronostico")
    def pronostico():
        datos = artifacts.get("predicciones.json")
        if datos is None:
            return {"disponible": False, "predicciones": []}
        return {"disponible": True, **datos}

    @app.get("/historico")
    def historico():
        hist = artifacts.get("historico.json")
        pred = artifacts.get("predicciones.json")
        return {
            "disponible": hist is not None,
            "origen": (hist or {}).get("origen"),
            "fecha": (hist or {}).get("fecha"),
            "mem": (hist or {}).get("mem", []),
            "fotos": (hist or {}).get("fotos", []),
            "predicciones": pred or {"predicciones": []},
        }

    @app.get("/metricas")
    def get_metricas():
        return metricas.resumen(_umbral())

    @app.get("/monitoreo/produccion")
    def monitoreo_produccion():
        filas = _leer_logs(aj.logs_dir)
        if not filas:
            return {
                "disponible": False,
                "mensaje": "Todavía no hay logs de /extraer.",
                "total": 0,
                "por_dia": [],
                "ultimas": [],
            }
        umbral = _umbral()
        por_dia: dict[str, list[dict]] = {}
        for f in filas:
            por_dia.setdefault(str(f.get("timestamp", ""))[:10], []).append(f)
        scores = [f["score_confianza"] for f in filas if f.get("score_confianza") is not None]
        fallidas = Counter(v for f in filas for v in f.get("validaciones_fallidas") or [])
        return {
            "disponible": True,
            "total": len(filas),
            "umbral_score": umbral,
            "pct_score_alto": round(100 * sum(s >= umbral for s in scores) / len(scores), 1)
            if scores
            else None,
            "pct_coincide_a_b": round(100 * sum(bool(f.get("coincide_a_b")) for f in filas)
                                      / len(filas), 1),
            "validaciones_fallidas": dict(fallidas.most_common()),
            "por_dia": [
                {
                    "dia": dia,
                    "peticiones": len(fs),
                    "latencia_ms_p50": _percentil([f.get("latencia_ms") or 0 for f in fs], 50),
                    "latencia_ms_p95": _percentil([f.get("latencia_ms") or 0 for f in fs], 95),
                }
                for dia, fs in sorted(por_dia.items())
            ],
            "ultimas": filas[-20:][::-1],
        }

    @app.get("/monitoreo/modelo")
    def monitoreo_modelo():
        datos = artifacts.get("monitoreo.json")
        if datos is None:
            return {"disponible": False, "alertas": []}
        return {"disponible": True, **datos}

    return app


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
app = crear_app()
