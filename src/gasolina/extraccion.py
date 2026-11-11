"""Extracción de precios de una foto (dueño: Modelos). Contrato 5.2 de
docs/instructivos/INSTRUCTIVO_GENERAL.md; lo consume pipelines/02_silver.py (una fila de
silver.precios por registro). NO cambiar el nombre ni quitar claves del resultado.

Algoritmo (fotos de bomba Shell/Puma; rótulos y tablas usan la asignación por cercanía):
  1. Pasada completa: OCR de la foto reescalada a ALTO_PASADA px.
  2. Segunda pasada: cada número con forma de precio y cada rótulo "Precio por galón" define un
     recorte de la foto original, que se amplía para que los dígitos midan ~ALTO_DIGITO px y se
     lee con varios preprocesamientos. Las lecturas se agrupan por posición (una pantallita) y
     votan, ponderadas por confianza.
  3. Cada pantallita se asigna al combustible de la etiqueta impresa de su panel ("Diesel",
     "Regular", "Super", "V-Power"); las que no tienen etiqueta legible se infieren con la
     secuencia de la marca (fuente "inferido").
  4. Ruta A: total / galones de "Esta Venta" verifica (fuente "ambas") o corrige un dígito
     ("corregido_por_ruta_A") de la pantallita del combustible despachado.
  5. V-Power se descarta; se devuelven super, regular y diesel.
"""

from __future__ import annotations

import time
from pathlib import Path

import numpy as np

from gasolina import __version__
from gasolina import reglas as R
from gasolina.metadata import leer_metadata, leer_metadata_bytes
from gasolina.ocr import cargar_imagen, crear_motor, leer_escalado

MODO_EXTRACCION = "real"

COMBUSTIBLES = ("super", "regular", "diesel")
MODALIDADES = ("autoservicio", "servicio_completo", None)
TIPOS_FOTO = ("rotulo", "bomba", "tabla_mem", "desconocido")

CLAVES_RESULTADO = (
    "archivo",
    "modo",
    "metadata",
    "registros",
    "tipo_foto",
    "validaciones",
    "score_confianza",
    "motor",
    "preproc",
    "tiempo_ms",
    "version_modelo",
    "detecciones_crudas",
)

CLAVES_REGISTRO = (
    "combustible",
    "precio_q_galon",
    "modalidad",
    "ubicacion",
    "confianza",
    "texto_fuente",
)

ALTO_PASADA = 2400          # px de alto para la pasada completa
ALTO_DIGITO = 56            # px de alto de los dígitos en la segunda pasada
PREPROCS_RECORTE = ("ninguno",)  # gris_clahe y binarizado en recortes empeoran (grilla)
MAX_RECORTES = 16
MARGEN_X, MARGEN_Y = 0.5, 0.9  # margen del recorte alrededor de un precio (en anchos / altos)


# --------------------------------------------------------------------------------------------
# Pasadas de OCR
# --------------------------------------------------------------------------------------------
def _recorte(img: np.ndarray, x1, y1, x2, y2):
    h, w = img.shape[:2]
    x1, y1 = max(0, int(x1)), max(0, int(y1))
    x2, y2 = min(w, int(x2)), min(h, int(y2))
    if x2 - x1 < 8 or y2 - y1 < 8:
        return None, (0, 0)
    return img[y1:y2, x1:x2], (x1, y1)


def _es_parcial(texto: str) -> bool:
    """Número cortado o mal leído ('33.8', '26', '4.89'): vale la pena releerlo de cerca."""
    t = texto.replace(" ", "")
    num = R.parsear_numero(t)
    if num is not None:  # '4.89' o '9.14': perdió el primer dígito
        return num[1] == 2 and num[0] < R.RANGO_CANDIDATO[0]
    digitos = sum(ch.isdigit() for ch in t)
    return digitos >= 2 and digitos / max(1, len(t)) >= 0.6


def _regiones_pantallitas(dets: list[dict], y_min: float = 0.0) -> list[tuple]:
    """Regiones (x1, y1, x2, y2, alto_digito) a releer: cada precio candidato, cada número
    parcial, cada rótulo 'Precio por galón' (la pantallita está justo arriba o abajo) y, si no hay
    pantallita encima, cada etiqueta de combustible (la pantallita está arriba, en su panel).
    Se ignora lo que está arriba de y_min (pantalla Esta Venta)."""
    regiones = []
    cands = R.candidatos_precio(dets)
    for d in cands:
        x1, y1, x2, y2 = d["bbox"]
        w, h = x2 - x1, y2 - y1
        regiones.append((x1 - MARGEN_X * w, y1 - MARGEN_Y * h, x2 + MARGEN_X * w,
                         y2 + MARGEN_Y * h, h))
    for d in dets:
        x1, y1, x2, y2 = d["bbox"]
        w, h = x2 - x1, y2 - y1
        if R.es_rotulo_precio(d["texto"]):
            h = min(h, 0.45 * w)  # bbox inclinadas: el alto real del texto es menor
            regiones.append((x1 - 0.25 * w, y1 - 3.0 * h, x2 + 0.25 * w, y2 + 3.5 * h, 1.4 * h))
        elif _es_parcial(d["texto"]) and y1 > y_min:
            regiones.append((x1 - 1.2 * h * 2.5, y1 - 0.9 * h, x2 + 1.2 * h * 2.5,
                             y2 + 0.9 * h, h))
    for e in R.etiquetas_combustible(dets):
        x1, y1, x2, y2 = e["bbox"]
        h = min(y2 - y1, 0.5 * (x2 - x1))
        cx = (x1 + x2) / 2
        reg = (cx - 2.4 * h * 2, y1 - 9 * h, cx + 2.4 * h * 2, y1, 1.3 * h)
        if reg[1] < y_min:
            continue
        cubierta = any(reg[0] <= R.centro(c["bbox"])[0] <= reg[2]
                       and reg[1] <= R.centro(c["bbox"])[1] <= reg[3] for c in cands)
        if not cubierta:
            regiones.append(reg)
    # quitar regiones casi duplicadas
    unicas = []
    for r in sorted(regiones, key=lambda r: (r[1], r[0])):
        cx, cy = (r[0] + r[2]) / 2, (r[1] + r[3]) / 2
        if all(abs(cx - (u[0] + u[2]) / 2) > 0.25 * (u[2] - u[0])
               or abs(cy - (u[1] + u[3]) / 2) > 0.25 * (u[3] - u[1]) for u in unicas):
            unicas.append(r)
    return unicas[:MAX_RECORTES]


def _segunda_pasada(motor, img: np.ndarray, dets_full: list[dict], y_min: float = 0.0
                    ) -> list[dict]:
    """Relee cada pantallita en un recorte ampliado de la foto original."""
    out = []
    for x1, y1, x2, y2, h_digito in _regiones_pantallitas(dets_full, y_min):
        rec, origen = _recorte(img, x1, y1, x2, y2)
        if rec is None or h_digito <= 0:
            continue
        alto = int(np.clip(rec.shape[0] * ALTO_DIGITO / h_digito, 48, 1200))
        for preproc in PREPROCS_RECORTE:
            for d in leer_escalado(motor, rec, alto, preproc, origen):
                d["pasada"] = f"recorte/{preproc}"
                out.append(d)
    return out


# --------------------------------------------------------------------------------------------
# Votación por pantallita
# --------------------------------------------------------------------------------------------
def _agrupar_pantallitas(candidatos: list[dict]) -> list[dict]:
    """Agrupa lecturas de la misma pantallita (centros cercanos) y vota el valor."""
    grupos: list[list[dict]] = []
    for c in sorted(candidatos, key=lambda c: -c["confianza"]):
        cx, cy = R.centro(c["bbox"])
        for g in grupos:
            gx, gy = R.centro(g[0]["bbox"])
            if (abs(cx - gx) < 0.5 * R.ancho(g[0]["bbox"])
                    and abs(cy - gy) < 0.7 * R.alto(g[0]["bbox"])):
                g.append(c)
                break
        else:
            grupos.append([c])

    pantallas = []
    for g in grupos:
        votos: dict[float, float] = {}
        for c in g:
            votos[c["valor"]] = votos.get(c["valor"], 0.0) + c["confianza"]
        valor, peso = max(votos.items(), key=lambda kv: kv[1])
        # Sesgo conocido del OCR en estos LCD: un "1" se lee como "7" (el marco del display
        # parece el segmento superior), nunca al revés. Si alguna lectura ve "1" donde la
        # ganadora ve "7" (y en lo demás coinciden), gana la del "1".
        for alt, w in sorted(votos.items(), key=lambda kv: -kv[1]):
            if alt != valor and R._es_7_a_1(valor, alt):
                valor, peso = alt, max(peso, w)
                break
        total = sum(votos.values())
        lecturas = [c for c in g if c["valor"] == valor]
        conf = float(np.mean([c["confianza"] for c in lecturas])) * (peso / total) ** 0.5
        bbox = tuple(float(np.median([c["bbox"][i] for c in g])) for i in range(4))
        pantallas.append({
            "valor": valor, "confianza": round(conf, 3), "bbox": bbox,
            "n_lecturas": len(g), "votos": {f"{k:.2f}": round(v, 2) for k, v in votos.items()},
            "texto": lecturas[0]["texto"],
        })
    return pantallas


def _filtrar_fila(pantallas: list[dict]) -> list[dict]:
    """En una bomba las pantallitas forman una fila: descarta números sueltos lejos de ella
    (marcas de la manguera, teclado, etc.) y grupos con una sola lectura débil."""
    if len(pantallas) <= 1:
        return pantallas
    fuertes = [p for p in pantallas if p["n_lecturas"] >= 2 or p["confianza"] >= 0.9] or pantallas
    y_med = float(np.median([R.centro(p["bbox"])[1] for p in fuertes]))
    h_med = float(np.median([R.alto(p["bbox"]) for p in fuertes]))
    return [p for p in pantallas
            if abs(R.centro(p["bbox"])[1] - y_med) < 6 * h_med
            and (p["n_lecturas"] >= 2 or p["confianza"] >= 0.6)]


# --------------------------------------------------------------------------------------------
# Resultado
# --------------------------------------------------------------------------------------------
def _ubicacion(marca: str | None, meta: dict) -> str | None:
    nombre = {"shell": "Shell", "puma": "Puma"}.get(marca)
    if meta.get("lat") is not None and meta.get("lon") is not None:
        coords = f"{meta['lat']:.3f},{meta['lon']:.3f}"
        return f"{nombre} ({coords})" if nombre else f"({coords})"
    return nombre


def _det_cruda(d: dict) -> dict:
    return {"texto": d["texto"], "confianza": round(float(d["confianza"]), 3),
            "bbox": [round(float(v)) for v in d["bbox"]]}


def extraer_precios(
    ruta: str | Path | bytes,
    motor: str = "rapidocr",
    preproc: str = "gris_clahe",
    fecha_carpeta: str | None = None,
    nombre: str | None = None,
    estrategia: str = "fusion",
    segunda_pasada: bool = True,
) -> dict:
    """Lee los precios de una foto (HEIC, JPG o PNG).

    Args:
        ruta: ruta a la imagen o sus bytes (columna `content` de bronze.fotos_precios).
        motor: "rapidocr" | "easyocr".
        preproc: preprocesamiento de la pasada completa
            ("ninguno" | "gris_clahe" | "gris_clahe_x2" | "binarizado").
        fecha_carpeta: fecha de respaldo (AAAA-MM-DD) si la foto no trae EXIF.
        nombre: nombre del archivo cuando `ruta` son bytes.
        estrategia: "fusion" (A+B) | "solo_B" (sin usar Esta Venta).
        segunda_pasada: releer cada pantallita en un recorte ampliado (más lento, más exacto).

    Returns:
        dict del contrato 5.2.
    """
    t0 = time.perf_counter()
    if isinstance(ruta, (bytes, bytearray)):
        archivo = Path(nombre or "foto").name
        meta = leer_metadata_bytes(bytes(ruta), archivo)
    else:
        ruta = Path(ruta)
        archivo = ruta.name
        meta = leer_metadata(ruta)

    validaciones: list[dict] = []
    if meta.get("fecha_hora") is None and fecha_carpeta:
        meta["fecha_hora"] = f"{fecha_carpeta}T00:00:00"
        validaciones.append(R._v("fecha", "advertencia",
                                 "Sin fecha EXIF: se usa la fecha de la carpeta."))

    resultado = {
        "archivo": archivo, "modo": MODO_EXTRACCION, "metadata": meta, "registros": [],
        "tipo_foto": "desconocido", "validaciones": validaciones, "score_confianza": 0.0,
        "motor": motor, "preproc": preproc, "tiempo_ms": 0, "version_modelo": __version__,
        "detecciones_crudas": [],
    }

    try:
        img = cargar_imagen(ruta)
    except Exception as e:  # noqa: BLE001 - archivo que no es imagen: se reporta, no truena
        validaciones.append(R._v("imagen_legible", "falla", f"No se pudo abrir la imagen: {e}"))
        resultado["tiempo_ms"] = round((time.perf_counter() - t0) * 1000)
        return resultado

    ocr = crear_motor(motor)
    dets = leer_escalado(ocr, img, min(ALTO_PASADA, max(img.shape[0], 32)), preproc)
    for d in dets:
        d["pasada"] = f"completa/{preproc}"
    ruta_a = R.leer_ruta_a(dets)
    y_min = ruta_a.get("y_galones") or 0.0  # nada de la pantalla Esta Venta es pantallita
    extra = _segunda_pasada(ocr, img, dets, y_min) if segunda_pasada else []
    todas = [d for d in dets + extra if R.centro(d["bbox"])[1] > y_min]

    pantallas = _filtrar_fila(_agrupar_pantallitas(R.candidatos_precio(todas)))
    tipo = R.clasificar_tipo_foto(dets, len(pantallas))
    marca = R.detectar_marca(dets)
    etiquetas = R.etiquetas_combustible(dets)

    if tipo == "bomba":
        asign = R.asignar_por_etiqueta(pantallas, etiquetas)
        asign, inferido = R.inferir_faltantes(pantallas, asign, marca)
    else:
        asign = R.asignar_por_cercania(pantallas, etiquetas)
        inferido = [False] * len(pantallas)
    for p, c, inf in zip(pantallas, asign, inferido):
        p["combustible"] = c
        p["fuente"] = "inferido" if inf else "ruta_B"

    if tipo != "bomba":
        ruta_a = {"precio_a": None}
    asignadas = [p for p in pantallas if p.get("combustible")]
    asignadas, despachado = R.fusionar(ruta_a, asignadas, estrategia)
    asignadas = R.reparar_orden(asignadas)

    modalidad = R.detectar_modalidad(dets)
    ubicacion = _ubicacion(marca, meta)
    registros, precios, confs = [], {}, []
    for p in sorted(asignadas, key=lambda p: R.centro(p["bbox"])[0]):
        c = p["combustible"]
        if c not in COMBUSTIBLES or c in precios:
            continue
        conf = p["confianza"]
        if p["fuente"] == "inferido":
            conf *= 0.7
        elif p["fuente"] == "ambas":
            conf = max(conf, 0.97)
        elif p["fuente"] == "corregido_por_ruta_A":
            conf = max(conf, 0.85)
        elif p["fuente"] == "corregido_por_reglas":
            conf *= 0.75
        conf = round(min(conf, 1.0), 3)
        precios[c] = p["valor"]
        confs.append(conf)
        detalle = f"OCR '{p['texto']}'"
        if p["fuente"] == "corregido_por_ruta_A":
            detalle = f"OCR {p['valor_ocr']:.2f} corregido con Esta Venta"
        elif p["fuente"] == "corregido_por_reglas":
            detalle = f"OCR {p['valor_ocr']:.2f} corregido por orden super>=regular"
        registros.append({
            "combustible": c,
            "precio_q_galon": round(p["valor"], 2),
            "modalidad": modalidad,
            "ubicacion": ubicacion,
            "confianza": conf,
            "texto_fuente": f"{c.upper()} {p['valor']:.2f} ({p['fuente']}; {detalle})",
        })

    from gasolina.config import cargar_config

    validaciones += R.validar(precios, ruta_a, cargar_config().get("calidad", {}))
    if despachado:
        validaciones.append(R._v("combustible_despachado", "ok",
                                 f"Esta Venta corresponde a {despachado}."))

    resultado.update({
        "registros": registros,
        "tipo_foto": tipo,
        "validaciones": validaciones,
        "score_confianza": R.score_confianza(confs, validaciones),
        "detecciones_crudas": [_det_cruda(d) for d in dets],
        "tiempo_ms": round((time.perf_counter() - t0) * 1000),
    })
    return resultado
