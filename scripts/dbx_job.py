"""Aplica, revierte o ejecuta el Job equipo-06-pipeline en Databricks.

Uso:
  python scripts/dbx_job.py aplicar    # deja el Job como pipelines/job.json (equipo_06_*, S3)
  python scripts/dbx_job.py revertir   # vuelve a docs/respaldo/job_antes_s3_20261116.json
  python scripts/dbx_job.py correr     # "Run now" y espera el resultado de cada tarea
  python scripts/dbx_job.py estado     # muestra rutas de notebooks y esquemas actuales

Lee DATABRICKS_HOST y DATABRICKS_TOKEN del entorno o del .env de la raíz del repo.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dbx_correr import _api, _env  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]
JOB_ID = 637916192930332
NUEVO = RAIZ / "pipelines/job.json"
RESPALDO = RAIZ / "docs/respaldo/job_antes_s3_20261116.json"


def estado(host, token):
    s = _api(host, token, "GET", f"/api/2.1/jobs/get?job_id={JOB_ID}")["settings"]
    print("notebooks:", [t["notebook_task"]["notebook_path"] for t in s["tasks"]])
    print("parámetros:", {p["name"]: p["default"] for p in s.get("parameters", [])
                          if p["name"].startswith(("esquema", "ruta"))})


def poner(host, token, archivo: Path):
    nuevo = json.loads(archivo.read_text())
    _api(host, token, "POST", "/api/2.1/jobs/reset", {"job_id": JOB_ID, "new_settings": nuevo})
    actual = _api(host, token, "GET", f"/api/2.1/jobs/get?job_id={JOB_ID}")["settings"]
    igual = actual == nuevo
    print("OK" if igual else "ATENCIÓN: el Job no quedó idéntico a", archivo.name)


def correr(host, token):
    run_id = _api(host, token, "POST", "/api/2.1/jobs/run-now", {"job_id": JOB_ID})["run_id"]
    print(f"run_id={run_id}", flush=True)
    while True:
        run = _api(host, token, "GET", f"/api/2.1/jobs/runs/get?run_id={run_id}")
        if run["state"].get("life_cycle_state") in ("TERMINATED", "SKIPPED", "INTERNAL_ERROR"):
            break
        time.sleep(20)
    print(run.get("run_page_url"))
    for t in run["tasks"]:
        seg = round((t.get("execution_duration") or 0) / 1000)
        print(f"{t['task_key']:7} {t['state'].get('result_state')} {seg} s")
        out = _api(host, token, "GET", f"/api/2.1/jobs/runs/get-output?run_id={t['run_id']}")
        if out.get("error"):
            print("   ERROR:", out["error"][:500])
    ok = run["state"].get("result_state") == "SUCCESS"
    print("RESULTADO:", "SUCCESS" if ok else "FALLÓ (puedes volver atrás con: revertir)")
    sys.exit(0 if ok else 1)


def main():
    accion = sys.argv[1] if len(sys.argv) > 1 else "estado"
    host, token = _env()
    if accion == "aplicar":
        poner(host, token, NUEVO)
    elif accion == "revertir":
        poner(host, token, RESPALDO)
    elif accion == "correr":
        correr(host, token)
    else:
        estado(host, token)


if __name__ == "__main__":
    main()
