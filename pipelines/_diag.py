# Databricks notebook source
# Diagnóstico temporal: dónde corre el notebook en un Job con git_source y por qué falla pip.
import json
import os
import subprocess
import sys

info = {"cwd": os.getcwd(), "padre": sorted(os.listdir(".."))[:30], "python": sys.version}
r = subprocess.run([sys.executable, "-m", "pip", "install", "--disable-pip-version-check", ".."],
                   capture_output=True, text=True)
info["rc"] = r.returncode
info["salida"] = r.stdout[-2000:] + "\n---ERR---\n" + r.stderr[-3000:]
dbutils.notebook.exit(json.dumps(info))  # noqa: F821
