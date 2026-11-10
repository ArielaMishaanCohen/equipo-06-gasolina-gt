#!/usr/bin/env python3
"""Manda fotos a /extraer para simular tráfico de producción (y prueba de humo).

Uso:
  python scripts/generar_trafico.py --url http://localhost:8000 --carpeta ../datos --repeticiones 5
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import requests

EXT = {".jpg", ".jpeg", ".png", ".heic", ".heif"}
COMB = ("diesel", "regular", "super", "vpower")


def fmt(v) -> str:
    return "—" if v is None else f"{v:.2f}"


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--url", default="http://localhost:8000")
    p.add_argument("--carpeta", type=Path, default=Path("../datos"))
    p.add_argument("--repeticiones", type=int, default=1)
    a = p.parse_args()

    fotos = sorted(f for f in a.carpeta.glob("*") if f.suffix.lower() in EXT)
    if not fotos:
        print(f"No hay fotos en {a.carpeta.resolve()}")
        return 1
    url = a.url.rstrip("/")
    try:
        h = requests.get(f"{url}/health", timeout=10).json()
        print(f"API {url}: v{h['version']} | artifacts {h['origen_artifacts']} | "
              f"modo {h['modo_extraccion']}\n")
    except requests.RequestException as e:
        print(f"La API no responde en {url}: {e}")
        return 1

    enc = f"{'#':>3} {'archivo':<16}" + "".join(f"{c:>9}" for c in COMB) + f"{'score':>7}{'ms':>8}"
    print(enc)
    print("-" * len(enc))
    errores, latencias, n = 0, [], 0
    for rep in range(a.repeticiones):
        for foto in fotos:
            n += 1
            t0 = time.perf_counter()
            try:
                with open(foto, "rb") as f:
                    r = requests.post(f"{url}/extraer", files={"foto": (foto.name, f)}, timeout=120)
                ms = (time.perf_counter() - t0) * 1000
                latencias.append(ms)
                if r.status_code != 200:
                    errores += 1
                    print(f"{n:>3} {foto.name:<16} ERROR {r.status_code}: {r.text[:80]}")
                    continue
                j = r.json()
                precios = j.get("precios") or {}
                score = j.get("score_confianza")
                print(f"{n:>3} {foto.name:<16}" + "".join(f"{fmt(precios.get(c)):>9}" for c in COMB)
                      + f"{fmt(score):>7}{ms:>8.0f}")
            except requests.RequestException as e:
                errores += 1
                print(f"{n:>3} {foto.name:<16} ERROR de red: {e}")

    if latencias:
        lat = sorted(latencias)
        p95 = lat[min(len(lat) - 1, int(0.95 * len(lat)))]
        print(f"\nPeticiones: {n} | errores: {errores} | "
              f"latencia p50 {lat[len(lat) // 2]:.0f} ms, p95 {p95:.0f} ms")
    return 1 if errores else 0


if __name__ == "__main__":
    sys.exit(main())
