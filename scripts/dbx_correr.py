"""Corre un notebook del repo en Databricks (serverless) y espera el resultado.

Uso:  python scripts/dbx_correr.py pipelines/01_bronze [--rama main] [--param clave=valor ...]

Lee DATABRICKS_HOST y DATABRICKS_TOKEN del entorno (o del .env). Usa Jobs `runs/submit` con
`git_source` (el repo es público), sin cluster: en Free Edition corre en cómputo serverless.
Imprime el estado final, el error si falla y la salida de `dbutils.notebook.exit` si existe.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO = "https://github.com/ArielaMishaanCohen/equipo-06-gasolina-gt"


def _env():
    env = Path(__file__).resolve().parents[1] / ".env"
    if env.is_file():
        for linea in env.read_text().splitlines():
            if "=" in linea and not linea.lstrip().startswith("#"):
                k, v = linea.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())
    return os.environ["DATABRICKS_HOST"].rstrip("/"), os.environ["DATABRICKS_TOKEN"]


def _api(host, token, metodo, ruta, cuerpo=None):
    datos = json.dumps(cuerpo).encode() if cuerpo is not None else None
    req = urllib.request.Request(f"{host}{ruta}", data=datos, method=metodo,
                                 headers={"Authorization": f"Bearer {token}",
                                          "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        sys.exit(f"HTTP {e.code} en {ruta}: {e.read().decode()[:2000]}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("notebook")
    ap.add_argument("--rama", default="main")
    ap.add_argument("--param", action="append", default=[])
    ap.add_argument("--timeout", type=int, default=3600)
    a = ap.parse_args()
    host, token = _env()
    params = dict(p.split("=", 1) for p in a.param)
    cuerpo = {
        "run_name": f"equipo6 {a.notebook} ({a.rama})",
        "git_source": {"git_url": REPO, "git_provider": "gitHub", "git_branch": a.rama},
        "tasks": [{"task_key": "t", "timeout_seconds": a.timeout,
                   "notebook_task": {"notebook_path": a.notebook, "source": "GIT",
                                     "base_parameters": params}}],
    }
    run_id = _api(host, token, "POST", "/api/2.1/jobs/runs/submit", cuerpo)["run_id"]
    print(f"run_id={run_id}", flush=True)
    t0 = time.time()
    while True:
        run = _api(host, token, "GET", f"/api/2.1/jobs/runs/get?run_id={run_id}")
        estado = run["state"]
        if estado.get("life_cycle_state") in ("TERMINATED", "SKIPPED", "INTERNAL_ERROR"):
            break
        time.sleep(15)
    print(f"url={run.get('run_page_url')}")
    print(f"resultado={estado.get('result_state')} ({int(time.time() - t0)} s) "
          f"{estado.get('state_message', '')}")
    tarea = run["tasks"][0]["run_id"]
    out = _api(host, token, "GET", f"/api/2.1/jobs/runs/get-output?run_id={tarea}")
    if out.get("error"):
        print("ERROR:", out["error"])
        print((out.get("error_trace") or "")[-3000:])
    if out.get("notebook_output", {}).get("result"):
        print("SALIDA:", out["notebook_output"]["result"][:3000])
    sys.exit(0 if estado.get("result_state") == "SUCCESS" else 1)


if __name__ == "__main__":
    main()
