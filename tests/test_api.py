"""Pruebas automatizadas de la API (contrato 5.5). Corren en el CI con las tablas Oro de ejemplo."""

import json

COMBUSTIBLES = {"super", "regular", "diesel"}


def test_health(cliente):
    r = cliente.get("/health")
    assert r.status_code == 200
    h = r.json()
    assert h["status"] == "ok"
    assert h["fuente_oro"] == "demo"
    assert set(h["tablas"]) == {"precio_semanal", "variacion_semanal", "features_modelo",
                                "predicciones", "metricas_modelo"}
    assert all(t["filas"] > 0 for t in h["tablas"].values())


def test_pagina_y_docs(cliente):
    assert "text/html" in cliente.get("/").headers["content-type"]
    assert cliente.get("/docs").status_code == 200


def test_precios_actual(cliente):
    r = cliente.get("/precios/actual")
    assert r.status_code == 200
    j = r.json()
    assert {p["combustible"] for p in j["precios"]} == COMBUSTIBLES
    assert all(20 <= p["precio_promedio"] <= 60 for p in j["precios"])
    assert j["semana_inicio"] == "2026-11-03"  # martes de la última semana completa


def test_precios_filtros_y_paginacion(cliente):
    r = cliente.get("/precios", params={"combustible": "diesel", "desde": "2026-10-01",
                                        "hasta": "2026-11-30", "limit": 3})
    assert r.status_code == 200
    j = r.json()
    assert j["limit"] == 3 and len(j["datos"]) == 3 and j["total"] >= 5
    assert {d["combustible"] for d in j["datos"]} == {"diesel"}
    assert all("2026-10-01" <= d["semana_inicio"] <= "2026-11-30" for d in j["datos"])
    assert {"dif_q", "direccion"} <= set(j["datos"][0])
    siguiente = cliente.get("/precios", params={"combustible": "diesel", "desde": "2026-10-01",
                                                "limit": 3, "offset": 3}).json()
    assert siguiente["datos"][0]["semana_inicio"] > j["datos"][-1]["semana_inicio"]


def test_precios_errores(cliente):
    assert cliente.get("/precios", params={"combustible": "vpower"}).status_code == 422
    assert cliente.get("/precios", params={"desde": "01/10/2026"}).status_code == 400
    assert cliente.get("/precios", params={"desde": "2026-12-01",
                                           "hasta": "2026-01-01"}).status_code == 400
    assert cliente.get("/precios", params={"limit": 5000}).status_code == 422


def test_prediccion(cliente):
    una = cliente.get("/prediccion", params={"combustible": "super"}).json()
    assert una["combustible"] == "super"
    assert una["prediccion"] in {"sube", "baja", "se_mantiene"}
    assert 0 <= una["probabilidad"] <= 1
    assert una["semana"] == "2026-11-10"
    todas = cliente.get("/prediccion").json()
    assert {p["combustible"] for p in todas["predicciones"]} == COMBUSTIBLES


def test_modelo_metricas(cliente):
    m = cliente.get("/modelo/metricas").json()
    assert {"accuracy_modelo", "accuracy_baseline", "supera_baseline"} <= set(m)


def test_registro_de_consultas(cliente):
    cliente.get("/health")
    cliente.get("/prediccion")
    logs = list((cliente.app.state.tmp / "logs").glob("consultas_*.jsonl"))
    assert len(logs) == 1
    lineas = [json.loads(x) for x in logs[0].read_text().splitlines()]
    assert [x["endpoint"] for x in lineas] == ["/health", "/prediccion"]
    assert lineas[0]["entorno"] == "test"
