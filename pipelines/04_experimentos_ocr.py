# Databricks notebook source
# MAGIC %md
# MAGIC # 04 — Experimentos de OCR contra revisión manual
# MAGIC Ejecutar después de `01_bronze`, con al menos 20 fotos etiquetadas.
# MAGIC Una corrida de MLflow por motor y preprocesamiento, con detalle CSV por foto.
# MAGIC El YAML recomendado se entrega a Producción para actualizar `config/config.yaml`
# MAGIC y los widgets de `02_silver`. Guía en `docs/modelos/CIERRE_MODELOS.md`.

# COMMAND ----------

import glob
import os
import shutil
import subprocess
import sys
import tempfile
import uuid

_src = os.path.join(tempfile.mkdtemp(prefix="gasolina-ocr-"), "src")
_wheels = f"/Volumes/workspace/equipo6_bronze/crudos/_wheels/ocr-{uuid.uuid4().hex}"
shutil.copytree(os.path.abspath(".."), _src, ignore=shutil.ignore_patterns(
    ".git", ".venv*", "tests", "docs", "presentacion", "artifacts_demo", "artifacts",
    "*.egg-info", "__pycache__"))
os.makedirs(_wheels, exist_ok=True)
subprocess.run([sys.executable, "-m", "pip", "wheel", "--no-deps", "-q", "-w", _wheels, _src],
               check=True)
WHEEL_GASOLINA = sorted(glob.glob(f"{_wheels}/gasolina-*.whl"))[-1]

# COMMAND ----------

# MAGIC %pip install $WHEEL_GASOLINA "numpy>=1.26,<2" "pandas>=2,<3" "protobuf>=4.25.3,<5"

# COMMAND ----------

dbutils.library.restartPython()

# COMMAND ----------

dbutils.widgets.text("catalogo", "workspace")
dbutils.widgets.text("esquema_bronze", "equipo_06_bronze")
dbutils.widgets.text("ruta_etiquetas", "")
dbutils.widgets.text("motores", "rapidocr")  # rapidocr,easyocr si está instalado el extra
dbutils.widgets.text("run_ids_reutilizar", "")  # corridas FINISHED del mismo conjunto y versión
dbutils.widgets.text("ruta_salida", "/Volumes/workspace/equipo6_bronze/crudos/evaluacion_ocr")

import importlib.util
import json
import math
import uuid
from datetime import datetime, timezone

import mlflow
import pandas as pd
import yaml
from pyspark.sql import functions as F

from gasolina import __version__
from gasolina.evaluacion import elegir_configuracion
from gasolina.ocr import MOTORES, PREPROCS
from gasolina.silver_extraccion import evaluar_resultados, extraer_lote

CATALOGO = dbutils.widgets.get("catalogo")
BRONZE = f"{CATALOGO}.{dbutils.widgets.get('esquema_bronze')}"
RUTA_ETIQUETAS = dbutils.widgets.get("ruta_etiquetas").strip()
RUTA_SALIDA = dbutils.widgets.get("ruta_salida").strip().rstrip("/")
motores = list(dict.fromkeys(m.strip() for m in dbutils.widgets.get("motores").split(",")))
if not motores or any(m not in MOTORES for m in motores):
    raise ValueError(f"Motores admitidos: {MOTORES}")
if not RUTA_ETIQUETAS:
    raise ValueError("Configura ruta_etiquetas con el CSV revisado manualmente")
etiquetas_df = spark.read.option("header", True).csv(RUTA_ETIQUETAS)
requeridas = {"foto", "combustible", "precio_q_galon"}
if not requeridas.issubset(etiquetas_df.columns):
    raise ValueError(f"Faltan columnas: {requeridas - set(etiquetas_df.columns)}")
etiquetas = [r.asDict() for r in etiquetas_df.collect()]
# Valida duplicados y precios antes de gastar tiempo en OCR.
resumen_inicial, _ = evaluar_resultados([], etiquetas)
if resumen_inicial["fotos_etiquetadas"] < 20:
    raise ValueError("La revisión requiere al menos 20 fotos distintas etiquetadas")
nombres = sorted({r["foto"].replace("\\", "/").rsplit("/", 1)[-1] for r in etiquetas})
fotos = (spark.table(f"{BRONZE}.fotos_precios").select("path", "content", "fecha_carpeta")
         .filter(F.element_at(F.split("path", "/"), -1).isin(nombres)))
presentes = [r["path"].rsplit("/", 1)[-1] for r in fotos.select("path").collect()]
if len(set(presentes)) != len(presentes):
    raise ValueError("Nombres de fotos ambiguos en Bronce")
if ausentes := set(nombres) - set(presentes):
    raise ValueError(f"Fotos etiquetadas ausentes en Bronce: {sorted(ausentes)}")

mlflow.set_tracking_uri("databricks")
mlflow.set_registry_uri("databricks-uc")
usuario = spark.sql("SELECT current_user()").first()[0]
mlflow.set_experiment(f"/Users/{usuario}/equipo06_ocr")
marca = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
corridas, comparativa, omitidos = [], [], []

# Permite reanudar una comparación cuando una configuración interrumpió el notebook.
# Se comprueba la verdad manual y se conservan los identificadores de las corridas originales.
for run_id in filter(None, (r.strip() for r in dbutils.widgets.get("run_ids_reutilizar").split(","))):
    previa = mlflow.get_run(run_id)
    params = {k: previa.data.params[k] for k in ("motor", "preproc")}
    if (previa.info.status != "FINISHED"
            or previa.data.tags.get("version_modelo") != __version__
            or params["motor"] not in motores or params["preproc"] not in PREPROCS):
        raise ValueError(f"Corrida incompatible para reanudar: {run_id}")
    resumen_path = mlflow.artifacts.download_artifacts(run_id=run_id, artifact_path="resumen.json")
    detalle_path = mlflow.artifacts.download_artifacts(run_id=run_id, artifact_path="exactitud_por_foto.csv")
    with open(resumen_path, encoding="utf-8") as archivo:
        resumen = json.load(archivo)
    detalle = pd.read_csv(detalle_path).to_dict("records")
    verdad_actual = {(r["foto"].replace("\\", "/").rsplit("/", 1)[-1], r["combustible"]):
                    float(r["precio_q_galon"]) for r in etiquetas}
    verdad_previa = {(r["foto"], combustible): dato["real"] for r in detalle
                     for combustible, dato in json.loads(r["detalle"]).items()}
    if verdad_actual != verdad_previa:
        raise ValueError(f"La corrida {run_id} usa etiquetas diferentes")
    corridas.append({"metricas": resumen, "por_foto": detalle,
                     "parametros": params, "mlflow_run_id": run_id})
    comparativa.append({**params, "mlflow_run_id": run_id,
                        "ejecucion": previa.data.params.get("ejecucion", "mapInPandas"), **resumen})

# COMMAND ----------

for motor in motores:
    for preproc in PREPROCS:
        if any(r["parametros"] == {"motor": motor, "preproc": preproc} for r in corridas):
            continue
        with mlflow.start_run(run_name=f"{motor}-{preproc}-{marca}") as run:
            mlflow.set_tags({"equipo": "06", "tipo": "evaluacion_ocr",
                             "version_modelo": __version__})
            mlflow.log_params({"motor": motor, "preproc": preproc,
                               "n_fotos": len(nombres), "segunda_pasada": True,
                               "estrategia": "fusion", "tolerancia_q": 0.005,
                               "ejecucion": "driver_streaming"})
            if motor == "easyocr" and importlib.util.find_spec("easyocr") is None:
                motivo = "Extra easyocr ausente en el driver y los workers"
                mlflow.set_tags({"estado": "omitido", "motivo": motivo})
                omitidos.append({"motor": motor, "preproc": preproc, "motivo": motivo})
                continue
            # El driver evita el límite de 1 GB por UDF de serverless. Se recibe
            # una foto por vez y solo se retienen las salidas pequeñas del OCR.
            resultados = []
            for foto in fotos.toLocalIterator():
                lote = pd.DataFrame([foto.asDict()])
                for salida in extraer_lote(iter([lote]), motor=motor, preproc=preproc,
                                           version_modelo=__version__):
                    resultados.extend(salida.to_dict("records"))
            resumen, detalle = evaluar_resultados(
                resultados, etiquetas)
            mlflow.log_metrics({k: float(v) for k, v in resumen.items()
                                if isinstance(v, (int, float)) and math.isfinite(v)})
            csv_detalle = pd.DataFrame(detalle).to_csv(index=False)
            mlflow.log_text(csv_detalle, "exactitud_por_foto.csv")
            mlflow.log_dict(resumen, "resumen.json")
            mlflow.set_tag("estado", "evaluado")
            corrida = {"metricas": resumen, "por_foto": detalle,
                       "parametros": {"motor": motor, "preproc": preproc},
                       "mlflow_run_id": run.info.run_id}
            corridas.append(corrida)
            comparativa.append({"motor": motor, "preproc": preproc,
                                "mlflow_run_id": run.info.run_id,
                                "ejecucion": "driver_streaming", **resumen})
            if RUTA_SALIDA:
                dbutils.fs.put(f"{RUTA_SALIDA}/{marca}/{motor}_{preproc}.csv",
                               csv_detalle, overwrite=True)

# COMMAND ----------

# Las latencias de driver y UDF corresponden a recursos diferentes. Al reanudar
# entre ambos entornos se desempata por exactitud/cobertura y orden de configuración.
seleccion = corridas
if len({r["ejecucion"] for r in comparativa}) > 1:
    seleccion = [{**r, "metricas": {**r["metricas"], "tiempo_ms_promedio": None}} for r in corridas]
ganador = elegir_configuracion(seleccion)
recomendacion = {"extraccion": ganador["parametros"]}
yaml_recomendado = yaml.safe_dump(recomendacion, allow_unicode=True, sort_keys=False)
tabla = pd.DataFrame(comparativa).sort_values(
    ["pct_precios_correctos", "pct_fotos_completas", "falsos_positivos", "tiempo_ms_promedio"],
    ascending=[False, False, True, True])
display(tabla)
print(f"Configuración recomendada: {ganador['parametros']}")
print(yaml_recomendado)
with mlflow.start_run(run_name=f"comparacion-{marca}"):
    mlflow.log_text(tabla.to_csv(index=False), "comparativa_ocr.csv")
    mlflow.log_text(yaml_recomendado, "config_extraccion_recomendada.yaml")
    mlflow.log_dict({"ganador": ganador["parametros"], "run_id": ganador["mlflow_run_id"],
                     "omitidos": omitidos}, "seleccion.json")
if RUTA_SALIDA:
    dbutils.fs.put(f"{RUTA_SALIDA}/{marca}/comparativa_ocr.csv", tabla.to_csv(index=False), True)
    dbutils.fs.put(f"{RUTA_SALIDA}/{marca}/config_extraccion_recomendada.yaml",
                   yaml_recomendado, True)
print("Actualizar motor/preproc de 02_silver con la recomendación y ejecutar reprocesar=true.")
