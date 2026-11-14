"""Adaptadores de OCR para mapInPandas en Plata (Modelos, Persona 1).

Spark vive en el notebook; estas funciones también se pueden probar sin un cluster.
Los errores de instalación/OCR se propagan: no son fotos sin precios legibles.
"""

from __future__ import annotations

import json
from datetime import date
from importlib.metadata import version


def comprobar_dependencias(motor="rapidocr"):
    """Importa los módulos nativos y ejecuta una lectura de prueba (sin descargar fotos)."""
    import numpy as np
    import pillow_heif

    from gasolina.ocr import crear_motor

    pillow_heif.register_heif_opener()
    crear_motor(motor).leer(np.full((64, 256, 3), 255, dtype=np.uint8))
    paquetes = ["gasolina", "pillow-heif", "pandas", "pyarrow"]
    paquetes += ["rapidocr_onnxruntime", "onnxruntime"] if motor == "rapidocr" else ["easyocr"]
    return {p: version(p) for p in paquetes}


def extraer_lote(lotes, motor="rapidocr", preproc="gris_clahe", version_modelo=None):
    """Una salida JSON por foto; content solo se recibe como bytes, nunca como ruta S3."""
    import pandas as pd

    from gasolina import __version__
    from gasolina.extraccion import extraer_precios

    if version_modelo is not None and __version__ != version_modelo:
        raise RuntimeError(f"Versión distinta en worker: {__version__} != {version_modelo}")
    for lote in lotes:
        filas = []
        for foto in lote.itertuples(index=False):
            fecha = foto.fecha_carpeta
            fecha = None if pd.isna(fecha) else str(fecha)[:10]
            resultado = extraer_precios(
                bytes(foto.content), nombre=foto.path.rsplit("/", 1)[-1],
                fecha_carpeta=fecha, motor=motor, preproc=preproc,
            )
            filas.append({"foto_origen": foto.path,
                          "resultado_json": json.dumps(resultado, ensure_ascii=False)})
        yield pd.DataFrame(filas, columns=["foto_origen", "resultado_json"])


def filas_candidatas(foto_origen, resultado):
    """Contrato 5.3 antes de calidad: una fila por precio, o un testigo sin precios.

    El bloque de Datos convierte el testigo a motivo/regla sin_precios_legibles.
    """
    fecha_hora = resultado.get("metadata", {}).get("fecha_hora")
    try:
        fecha = date.fromisoformat(str(fecha_hora)[:10]) if fecha_hora else None
    except ValueError:
        fecha = None
    base = {
        "fecha": fecha, "foto_origen": foto_origen,
        "motor": resultado["motor"], "version_modelo": resultado["version_modelo"],
    }
    return [
        {**base, "combustible": r.get("combustible"),
         "precio_q_galon": r.get("precio_q_galon"),
         "modalidad": (r.get("modalidad") or "").strip() or "no_indica",
         "ubicacion": (r.get("ubicacion") or "").strip() or "no_indica",
         "confianza": r.get("confianza", resultado.get("score_confianza", 0.0))}
        for r in (resultado.get("registros") or [{}])
    ]


def candidatos_lote(lotes):
    """Explota los resultados ya extraídos sin volver a ejecutar el OCR."""
    import pandas as pd

    columnas = ["fecha", "combustible", "precio_q_galon", "modalidad", "ubicacion",
                "foto_origen", "confianza", "motor", "version_modelo"]
    for lote in lotes:
        filas = [fila for foto in lote.itertuples(index=False)
                 for fila in filas_candidatas(foto.foto_origen, json.loads(foto.resultado_json))]
        yield pd.DataFrame(filas, columns=columnas)


def evaluar_resultados(resultados, etiquetas):
    """Usa el evaluador existente; rechaza nombres ambiguos o etiquetas duplicadas.

    Devuelve resumen y detalle plano para display y exportación CSV en el notebook.
    Las fotos etiquetadas ausentes se cuentan como no encontradas, sin inflar aciertos.
    """
    from gasolina.evaluacion import comparar

    verdad, nombres = {}, set()
    for etiqueta in etiquetas:
        nombre = etiqueta["foto"].replace("\\", "/").rsplit("/", 1)[-1]
        combustible = etiqueta["combustible"].strip().lower()
        if combustible not in {"super", "regular", "diesel"}:
            raise ValueError(f"Combustible inválido en etiquetas: {combustible}")
        precios = verdad.setdefault(nombre, {})
        if combustible in precios:
            raise ValueError(f"Etiqueta duplicada: {nombre}, {combustible}")
        precios[combustible] = {
            "precio": float(etiqueta["precio_q_galon"]),
            "lectura": etiqueta.get("lectura") or "a_simple_vista",
        }
    if not verdad:
        raise ValueError("etiquetas.csv no contiene precios etiquetados")
    pred = {}
    for foto in resultados:
        nombre = foto["foto_origen"].rsplit("/", 1)[-1]
        if nombre not in verdad:
            continue
        if nombre in nombres:
            raise ValueError(f"Nombre de foto ambiguo en Bronce: {nombre}")
        nombres.add(nombre)
        pred[nombre] = json.loads(foto["resultado_json"])
    evaluacion = comparar(pred, verdad)
    resumen = {k: v for k, v in evaluacion["metricas"].items() if k != "pct_por_lectura"}
    resumen.update(fotos_etiquetadas=len(verdad), fotos_evaluadas=len(pred),
                   fotos_ausentes=len(set(verdad) - set(pred)))
    detalle = []
    for foto in evaluacion["por_foto"]:
        estados = [d["estado"] for d in foto["detalle"].values()]
        correctos = estados.count("correcto")
        detalle.append({
            "foto": foto["foto"], "etiquetados": len(estados), "correctos": correctos,
            "incorrectos": sum(e.startswith("incorrecto") for e in estados),
            "no_encontrados": estados.count("no_encontrado"),
            "sin_etiqueta": len(foto["sin_etiqueta"]),
            "pct_precios_correctos": round(100 * correctos / len(estados), 1),
            "tiempo_ms": foto["tiempo_ms"], "foto_en_bronce": foto["foto"] in pred,
            "detalle": json.dumps(foto["detalle"], ensure_ascii=False),
        })
    return resumen, detalle
