"""Reglas de negocio de la extracción: normalización, etiquetas, asignación, ruta A, fusión y
validaciones (dueño: Modelos). Todo aquí es puro (sin OCR ni imágenes) para poder probarlo con
detecciones sintéticas.

Una detección es {"texto": str, "confianza": float, "bbox": (x1, y1, x2, y2)}.

Vocabulario:
  - Pantallita: display "Precio por galón" de una bomba (ruta B). Una por combustible.
  - Ruta A: pantalla "Esta Venta" (total en Q y galones). total / galones = precio del
    combustible despachado; sirve para verificar o corregir una pantallita.
  - Etiqueta: texto impreso con el nombre del combustible ("Diesel", "ION Diesel", "Regular",
    "Super", "V-Power"). Cada pantallita se asigna a la etiqueta de su mismo panel (abajo de ella),
    nunca solo por posición: el orden cambia entre bombas y entre lados de la misma bomba.
"""

from __future__ import annotations

import itertools
import re
import statistics
import unicodedata

FUENTES = ("ruta_A", "ruta_B", "ambas", "corregido_por_ruta_A", "corregido_por_reglas",
           "inferido")
ESTADOS = ("ok", "falla", "advertencia")
ESTRATEGIAS = ("solo_A", "solo_B", "fusion")

COMBUSTIBLES_CONTRATO = ("super", "regular", "diesel")
# Orden de izquierda a derecha de los paneles por marca (el lado opuesto de la bomba va al revés).
SECUENCIAS = {
    "shell": ("diesel", "regular", "super", "vpower"),
    "puma": ("diesel", "regular", "super"),
}
RANGO_CANDIDATO = (15.0, 60.0)  # Q/galón para considerar un número como precio
TOLERANCIA_RUTA_A = 0.011  # total/galones redondeado puede diferir 1 centavo


# --------------------------------------------------------------------------------------------
# Utilidades
# --------------------------------------------------------------------------------------------
def centro(bbox) -> tuple[float, float]:
    x1, y1, x2, y2 = bbox
    return (x1 + x2) / 2, (y1 + y2) / 2


def ancho(bbox) -> float:
    return max(1.0, bbox[2] - bbox[0])


def alto(bbox) -> float:
    return max(1.0, bbox[3] - bbox[1])


def _sin_acentos(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c))


def _letras(texto: str) -> str:
    return re.sub(r"[^a-z]", "", _sin_acentos(texto).lower())


# --------------------------------------------------------------------------------------------
# Números
# --------------------------------------------------------------------------------------------
def parsear_numero(texto: str) -> tuple[float, int] | None:
    """Texto de OCR -> (valor, número de decimales) o None.

    "33.45" -> (33.45, 2); "3 3.4 5" -> (33.45, 2); "29:59" -> (29.59, 2); "Q33,45" -> (33.45, 2);
    "3345" -> (33.45, 2) (las pantallitas no siempre muestran el punto); "3.664" -> (3.664, 3);
    "10000" -> (100.0, 2); basura -> None.
    """
    if texto is None:
        return None
    t = str(texto).strip().upper().replace(" ", "")
    t = t.lstrip("Q").replace(",", ".").replace(":", ".")
    t = t.strip("|-_'\"`~")
    if re.fullmatch(r"\d{1,3}\.\d{2,3}", t):
        return float(t), len(t.split(".")[1])
    if re.fullmatch(r"\d{4,5}", t):  # punto perdido: 2 decimales
        return float(t[:-2] + "." + t[-2:]), 2
    return None


def normalizar_numero(texto: str) -> float | None:
    """'3709' -> 37.09, '37,09' -> 37.09, 'Q33.45' -> 33.45, basura -> None."""
    r = parsear_numero(texto)
    return r[0] if r else None


def es_precio(texto: str, rango: tuple[float, float] = RANGO_CANDIDATO) -> float | None:
    """Valor si el texto es un precio por galón plausible (2 decimales, dentro del rango)."""
    r = parsear_numero(texto)
    if not r or r[1] != 2:
        return None
    return r[0] if rango[0] <= r[0] <= rango[1] else None


def digitos_distintos(a: float, b: float) -> int:
    """Cuántos dígitos difieren entre dos precios con 2 decimales (99 si tienen distinto largo)."""
    sa, sb = f"{a:.2f}", f"{b:.2f}"
    if len(sa) != len(sb):
        return 99
    return sum(x != y for x, y in zip(sa, sb))


# --------------------------------------------------------------------------------------------
# Palabras clave
# --------------------------------------------------------------------------------------------
_PATRONES_COMBUSTIBLE = (
    ("vpower", ("vpower", "power", "vpow")),
    ("diesel", ("diesel", "iesel", "diese", "dlesel", "diesei", "acpm")),
    ("regular", ("regular", "egular", "regula", "gular")),
    ("super", ("super", "uper", "supe", "premium")),
)


def detectar_combustible(texto: str) -> str | None:
    """'ION Diesel' -> 'diesel', 'Súper' -> 'super', 'V-Power' -> 'vpower', 'egular' -> 'regular'.
    Solo textos cortos (las frases largas de publicidad no cuentan)."""
    t = _letras(texto)
    if not t or len(t) > 16:
        return None
    if t in ("sup", "reg", "dsl"):
        return {"sup": "super", "reg": "regular", "dsl": "diesel"}[t]
    for combustible, claves in _PATRONES_COMBUSTIBLE:
        if any(c in t for c in claves):
            return combustible
    return None


def detectar_modalidad(detecciones: list[dict]) -> str | None:
    texto = " ".join(_letras(d["texto"]) for d in detecciones)
    if "autoservicio" in texto or "selfservice" in texto:
        return "autoservicio"
    if "serviciocompleto" in texto or "fullservice" in texto or "completo" in texto:
        return "servicio_completo"
    return None


def detectar_marca(detecciones: list[dict]) -> str | None:
    t = " ".join(_letras(d["texto"]) for d in detecciones)
    if "puma" in t or "cleantec" in t or "iondiesel" in t:
        return "puma"
    if "shell" in t or "fuelsave" in t or "vpower" in t:
        return "shell"
    return None


def es_rotulo_precio(texto: str) -> bool:
    t = _letras(texto)
    return "precio" in t or "galon" in t or "porgal" in t


def clasificar_tipo_foto(detecciones: list[dict], n_precios: int) -> str:
    """bomba (pantallitas de dispensador) | tabla_mem | rotulo | desconocido."""
    palabras = [_letras(d["texto"]) for d in detecciones]
    t = " ".join(palabras)
    if any(k in t for k in ("estaventa", "galones", "preciopor", "porgalon")):
        return "bomba"
    if any(k in t for k in ("ministerio", "energiayminas", "referencia")) or "mem" in palabras:
        if n_precios >= 3:
            return "tabla_mem"
    # Paneles de dispensador Shell/Puma sin rótulos legibles (FuelSave, V-Power, CLEANTEC...)
    if detectar_marca(detecciones) and (n_precios >= 2 or leer_ruta_a(detecciones)["precio_a"]):
        return "bomba"
    if n_precios >= 1:
        return "rotulo"
    return "desconocido"


# --------------------------------------------------------------------------------------------
# Ruta A: pantalla "Esta Venta"
# --------------------------------------------------------------------------------------------
def leer_ruta_a(detecciones: list[dict]) -> dict:
    """Busca galones (3 decimales) y, justo encima, el total de la venta.

    Devuelve {"total", "galones", "precio_a", "confianza", "y_galones"} (None si no se pudo);
    y_galones es el borde inferior de los galones (lo de arriba no son pantallitas).
    """
    vacio = {"total": None, "galones": None, "precio_a": None, "confianza": None,
             "y_galones": None}
    galones = []
    for d in detecciones:
        r = parsear_numero(d["texto"])
        if r and r[1] == 3 and 0.3 <= r[0] <= 60:
            galones.append((d, r[0]))
    mejor = None
    for dg, g in galones:
        gx, gy = centro(dg["bbox"])
        for dt in detecciones:
            if dt is dg:
                continue
            r = parsear_numero(dt["texto"])
            if not r or r[1] != 2 or r[0] < 10:
                continue
            tx, ty = centro(dt["bbox"])
            # el total va arriba de los galones y alineado en x
            if not (0 < gy - ty < 3 * alto(dg["bbox"]) and abs(tx - gx) < ancho(dt["bbox"])):
                continue
            conf = min(dg["confianza"], dt["confianza"])
            if mejor is None or conf > mejor["confianza"]:
                mejor = {"total": r[0], "galones": g, "precio_a": round(r[0] / g, 2),
                         "confianza": round(conf, 3), "y_galones": dg["bbox"][3]}
    return mejor or vacio


# --------------------------------------------------------------------------------------------
# Ruta B: asignar pantallitas a combustibles
# --------------------------------------------------------------------------------------------
def candidatos_precio(detecciones: list[dict], rango=RANGO_CANDIDATO) -> list[dict]:
    """Detecciones que parecen precio por galón (2 decimales y dentro del rango). Excluye el total
    de la venta (> rango) y los galones (3 decimales)."""
    out = []
    for d in detecciones:
        v = es_precio(d["texto"], rango)
        if v is not None:
            out.append({**d, "valor": v})
    return out


def etiquetas_combustible(detecciones: list[dict]) -> list[dict]:
    out = []
    for d in detecciones:
        c = detectar_combustible(d["texto"])
        if c:
            out.append({**d, "combustible": c})
    return out


def _costo(pantalla: dict, etiqueta: dict) -> float | None:
    """Costo de asignar la etiqueta a la pantallita (None = imposible). La etiqueta va en el mismo
    panel: debajo (o a la par) de la pantallita y alineada en x."""
    px, py = centro(pantalla["bbox"])
    ex, ey = centro(etiqueta["bbox"])
    wp, hp = ancho(pantalla["bbox"]), alto(pantalla["bbox"])
    dx, dy = abs(ex - px), ey - py
    if dy < -0.6 * hp or dy > 12 * hp or dx > 1.6 * wp:
        return None
    return dx / wp + 0.08 * abs(dy) / hp


def asignar_por_etiqueta(pantallas: list[dict], etiquetas: list[dict]) -> list[str | None]:
    """Asignación óptima (húngaro) pantallita -> combustible por etiqueta impresa.
    Cada etiqueta se usa una vez; una pantallita sin etiqueta válida queda en None."""
    import numpy as np
    from scipy.optimize import linear_sum_assignment

    n, m = len(pantallas), len(etiquetas)
    if n == 0:
        return []
    SIN, IMPOSIBLE = 1.5, 1e6  # costo de dejar una pantallita sin etiqueta / asignación inválida
    costos = [[_costo(p, e) for e in etiquetas] for p in pantallas]
    matriz = np.full((n, m + n), SIN)
    for k in range(n):
        for i in range(m):
            matriz[k, i] = IMPOSIBLE if costos[k][i] is None else costos[k][i]
    filas, cols = linear_sum_assignment(matriz)
    mejor = [None] * n
    for k, i in zip(filas, cols):
        if i < m and matriz[k, i] < IMPOSIBLE:
            mejor[k] = int(i)
    asign = [etiquetas[i]["combustible"] if i is not None else None for i in mejor]
    # Un combustible no puede aparecer dos veces: se queda con la etiqueta más cercana.
    for c in set(a for a in asign if a):
        idx = [k for k, a in enumerate(asign) if a == c]
        if len(idx) > 1:
            keep = min(idx, key=lambda k: costos[k][mejor[k]])
            for k in idx:
                if k != keep:
                    asign[k] = None
    return asign


def inferir_faltantes(pantallas: list[dict], asign: list[str | None], marca: str | None
                      ) -> tuple[list[str | None], list[bool]]:
    """Completa las pantallitas sin etiqueta con la secuencia de paneles de la marca.

    Las pantallitas, ordenadas por x, se colocan en posiciones crecientes de la secuencia (en
    cualquiera de los dos sentidos, porque el otro lado de la bomba va al revés). Se elige la
    colocación que coincide con todas las etiquetas encontradas, con menos huecos y, sin
    etiquetas, la que respeta V-Power >= Super >= Regular. Devuelve (asignación, inferido).
    """
    n = len(pantallas)
    inferido = [False] * n
    if n == 0 or all(asign):
        return asign, inferido
    orden = sorted(range(n), key=lambda k: centro(pantallas[k]["bbox"])[0])
    secuencias = [SECUENCIAS[marca]] if marca in SECUENCIAS else list(SECUENCIAS.values())

    mejor, mejor_puntos = None, None
    for sec in secuencias:
        for direccion in (sec, tuple(reversed(sec))):
            if n > len(direccion):
                continue
            for pos in itertools.combinations(range(len(direccion)), n):
                slots = {k: pos[j] for j, k in enumerate(orden)}
                coincide = sum(1 for k in range(n) if asign[k] and asign[k] == direccion[slots[k]])
                if any(asign[k] and asign[k] != direccion[slots[k]] for k in range(n)):
                    continue
                huecos = pos[-1] - pos[0] + 1 - n
                puntos = (coincide, -huecos, _puntos_por_precio(pantallas, slots, direccion))
                if mejor_puntos is None or puntos > mejor_puntos:
                    mejor, mejor_puntos = (direccion, slots), puntos
    if mejor is None:
        return asign, inferido
    direccion, slots = mejor
    nueva = list(asign)
    for k in range(n):
        if nueva[k] is None:
            nueva[k] = direccion[slots[k]]
            inferido[k] = True
    return nueva, inferido


def _puntos_por_precio(pantallas, slots, direccion) -> float:
    """Cuánto respeta la asignación V-Power >= Super >= Regular (-2 a 2)."""
    val = {direccion[s]: pantallas[k].get("valor") for k, s in slots.items()}
    puntos = 0.0
    for a, b in (("vpower", "super"), ("super", "regular")):
        if val.get(a) is not None and val.get(b) is not None:
            puntos += 1 if val[a] >= val[b] else -1
    return puntos


def asignar_por_cercania(precios: list[dict], etiquetas: list[dict]) -> list[str | None]:
    """Para rótulos y tablas: la etiqueta más cercana a la izquierda en la misma fila, o justo
    encima/debajo."""
    asign = []
    for p in precios:
        px, py = centro(p["bbox"])
        hp = alto(p["bbox"])
        mejor, mejor_d = None, None
        for e in etiquetas:
            ex, ey = centro(e["bbox"])
            misma_fila = abs(ey - py) < 0.8 * hp and ex < px
            vertical = abs(ex - px) < 2 * ancho(p["bbox"]) and abs(ey - py) < 3 * hp
            if not (misma_fila or vertical):
                continue
            d = abs(ex - px) + 2 * abs(ey - py)
            if mejor_d is None or d < mejor_d:
                mejor, mejor_d = e["combustible"], d
        asign.append(mejor)
    return asign


# --------------------------------------------------------------------------------------------
# Fusión A + B
# --------------------------------------------------------------------------------------------
def fusionar(ruta_a: dict, pantallas: list[dict], estrategia: str = "fusion"
             ) -> tuple[list[dict], str | None]:
    """Cruza las pantallitas (ya asignadas, con "combustible" y "valor") con la ruta A.

    - Si una pantallita coincide con precio_a (± 1 centavo): fuente "ambas".
    - Si ninguna coincide pero una difiere en un solo dígito: se corrige a precio_a
      ("corregido_por_ruta_A"); es el error típico del OCR en 7 segmentos (1<->7, 3<->9, 5<->6).
    Devuelve (pantallas actualizadas, combustible_despachado).
    """
    if estrategia not in ESTRATEGIAS:
        raise ValueError(f"Estrategia desconocida: {estrategia}")
    pa = ruta_a.get("precio_a")
    if estrategia == "solo_B" or pa is None or not pantallas:
        return pantallas, None
    out = [dict(p) for p in pantallas]
    for p in out:
        p.setdefault("fuente", "ruta_B")
    iguales = [p for p in out if p.get("valor") is not None
               and abs(p["valor"] - pa) <= TOLERANCIA_RUTA_A]
    if iguales:
        for p in iguales:
            p["fuente"] = "ambas"
        return out, iguales[0].get("combustible")

    def corregir(p):
        p["valor_ocr"], p["valor"], p["fuente"] = p["valor"], pa, "corregido_por_ruta_A"
        return out, p.get("combustible")

    # 1) Alguna pasada de OCR sí leyó precio_a en esa pantallita (perdió la votación).
    con_voto = []
    for p in out:
        peso = sum(w for v, w in (p.get("votos") or {}).items()
                   if abs(float(v) - pa) <= TOLERANCIA_RUTA_A)
        if peso > 0:
            con_voto.append((peso, p))
    if con_voto:
        return corregir(max(con_voto, key=lambda t: t[0])[1])
    # 2) Una sola pantallita a un dígito de distancia.
    cercanas = [p for p in out if p.get("valor") is not None
                and digitos_distintos(p["valor"], pa) == 1]
    if len(cercanas) == 1:
        return corregir(cercanas[0])
    return out, None


# Confusiones típicas del OCR en displays de 7 segmentos.
CONFUSIONES = {"7": "1", "1": "7", "8": "6", "6": "8", "9": "3", "3": "9", "5": "6", "0": "8"}
ANCLADAS = ("ambas", "corregido_por_ruta_A")
ORDEN_PRECIOS = (("vpower", "super"), ("super", "regular"))


def _alternativas(p: dict) -> list[tuple[float, float]]:
    """(valor, peso) alternativos de una pantallita: otros votos y cambios de un dígito
    confundible (peso 0)."""
    alts = {}
    for v, w in (p.get("votos") or {}).items():
        if abs(float(v) - p["valor"]) > 1e-9:
            alts[round(float(v), 2)] = max(alts.get(round(float(v), 2), 0.0), w)
    s = f"{p['valor']:.2f}"
    for i, ch in enumerate(s):
        if ch in CONFUSIONES:
            v = round(float(s[:i] + CONFUSIONES[ch] + s[i + 1:]), 2)
            alts.setdefault(v, 0.0)
    return list(alts.items())


def _es_7_a_1(a: float, b: float) -> bool:
    """True si b es a con uno o más '7' cambiados por '1' (y nada más)."""
    sa, sb = f"{a:.2f}", f"{b:.2f}"
    return len(sa) == len(sb) and sa != sb and all(
        x == y or (x == "7" and y == "1") for x, y in zip(sa, sb))


def reparar_orden(pantallas: list[dict]) -> list[dict]:
    """Si se viola V-Power >= Super >= Regular, prueba lecturas alternativas (otros votos o un
    dígito confundible) en las pantallitas no ancladas por la ruta A y se queda con el cambio
    mínimo que cumple el orden. Fuente "corregido_por_reglas"."""
    por_c = {p.get("combustible"): p for p in pantallas if p.get("combustible")}

    def cumple(vals):
        return all(vals[a] >= vals[b] for a, b in ORDEN_PRECIOS if a in vals and b in vals)

    actuales = {c: p["valor"] for c, p in por_c.items() if c in ("vpower", "super", "regular")}
    if cumple(actuales):
        return pantallas
    opciones = {}
    for c, v in actuales.items():
        p = por_c[c]
        opciones[c] = [(v, None)]
        if p.get("fuente") not in ANCLADAS:
            opciones[c] += [(a, w) for a, w in _alternativas(p)]
    mejor, mejor_score = None, None
    claves = list(opciones)
    for combo in itertools.product(*(opciones[c] for c in claves)):
        vals = {c: v for c, (v, _) in zip(claves, combo)}
        if not cumple(vals):
            continue
        cambios = [(c, v, w) for c, (v, w) in zip(claves, combo) if w is not None]
        # menos cambios; luego preferir 7 -> 1 (sesgo conocido del OCR); luego más votos
        n_7a1 = sum(_es_7_a_1(por_c[c]["valor"], v) for c, v, _ in cambios)
        score = (-len(cambios), n_7a1, sum(w for _, _, w in cambios))
        if mejor_score is None or score > mejor_score:
            mejor, mejor_score = vals, score
    if mejor is None:
        return pantallas
    for c, v in mejor.items():
        p = por_c[c]
        if abs(v - p["valor"]) > 1e-9:
            p["valor_ocr"], p["valor"], p["fuente"] = p["valor"], v, "corregido_por_reglas"
    return pantallas


# --------------------------------------------------------------------------------------------
# Validaciones y score
# --------------------------------------------------------------------------------------------
def _v(nombre: str, estado: str, mensaje: str) -> dict:
    return {"nombre": nombre, "estado": estado, "mensaje": mensaje}


def validar(precios: dict, ruta_a: dict, reglas: dict | None = None,
            referencia: dict | None = None) -> list[dict]:
    """precios: {combustible: valor}. Devuelve la lista de validaciones del contrato 5.2."""
    reglas = reglas or {}
    rmin = reglas.get("rango_precio", {}).get("min", 20.0)
    rmax = reglas.get("rango_precio", {}).get("max", 60.0)
    out = []

    if not precios:
        out.append(_v("formato_y_rango", "falla", "No se leyó ningún precio."))
    else:
        fuera = {c: v for c, v in precios.items() if not (rmin <= v <= rmax)}
        out.append(_v("formato_y_rango", "falla" if fuera else "ok",
                      f"Fuera de [{rmin}, {rmax}]: {fuera}" if fuera
                      else f"{len(precios)} precios con 2 decimales en [{rmin}, {rmax}]."))

    s, r = precios.get("super"), precios.get("regular")
    if s is not None and r is not None:
        out.append(_v("orden_gasolinas", "ok" if s >= r else "falla",
                      f"super {s:.2f} {'>=' if s >= r else '<'} regular {r:.2f}"))
        dif = s - r
        out.append(_v("diferencias_tipicas", "ok" if 0.2 <= dif <= 3.0 else "advertencia",
                      f"super - regular = {dif:.2f} (típico entre 0.20 y 3.00)"))
    else:
        out.append(_v("orden_gasolinas", "advertencia", "Falta super o regular para comparar."))

    pa = ruta_a.get("precio_a")
    if pa is None:
        out.append(_v("venta_entre_galones", "advertencia", "No se leyó la pantalla Esta Venta."))
    else:
        coincide = [c for c, v in precios.items() if abs(v - pa) <= TOLERANCIA_RUTA_A]
        out.append(_v("venta_entre_galones", "ok" if coincide else "advertencia",
                      f"{ruta_a['total']:.2f} / {ruta_a['galones']:.3f} = {pa:.2f}"
                      + (f" = {coincide[0]}" if coincide else " (no coincide con ninguna)")))

    if referencia:
        lejos = {c: (v, referencia[c]) for c, v in precios.items()
                 if referencia.get(c) and abs(v - referencia[c]) > 3.0}
        out.append(_v("referencia_mem", "advertencia" if lejos else "ok",
                      f"A más de Q3 de la referencia: {lejos}" if lejos
                      else "Dentro de Q3 de la referencia del MEM."))
    return out


def score_confianza(confianzas_ocr: list[float], validaciones: list[dict]) -> float:
    """Promedio de confianzas de OCR, penalizado por fallas (-0.25) y advertencias (-0.05)."""
    if not confianzas_ocr:
        return 0.0
    base = statistics.fmean(confianzas_ocr)
    for v in validaciones:
        if v["estado"] == "falla":
            base -= 0.25
        elif v["estado"] == "advertencia":
            base -= 0.05
    return round(min(1.0, max(0.0, base)), 3)
