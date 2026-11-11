"""Fuentes externas: MEM (PDF) y FRED (CSV) (dueño: Datos).

MEM: los informes semanales de la Dirección General de Hidrocarburos traen una tabla
"precios promedio de las últimas semanas" (área metropolitana / Ciudad de Guatemala,
modalidad autoservicio) con 7 fechas de monitoreo. Cada informe se parsea con pdfplumber y los
informes se consolidan. Los informes de enero a julio de 2025 son imágenes dentro del PDF:
esas tablas se transcribieron a mano ("curación manual de fuente externa") a un CSV con la misma
forma que devuelve `parsear_informe_mem` y se mezclan con `consolidar_mem`.

Las fechas de monitoreo no siempre caen en lunes (a veces martes o jueves). Para el contrato 5.4
se asignan a la semana martes-lunes con `semana_inicio` y, si una semana tiene varios
monitoreos, se promedian (`a_semanal`).

Funciones:
  - parsear_informe_mem(ruta_pdf) -> DataFrame (fecha, combustible, precio_promedio,
      modalidad, fuente_pdf)
  - consolidar_mem(dfs) -> sin duplicados (misma fecha y combustible: gana el informe más reciente)
  - semana_inicio(fecha) -> martes de la semana martes-lunes
  - a_semanal(df, region, fuente_urls) -> tabla con columnas de `mem_referencia.csv`
  - descargar_fred(serie, destino) / leer_fred(ruta_csv)
"""

from __future__ import annotations

import logging
import re
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd

log = logging.getLogger(__name__)

URL_FRED = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={serie}"
SERIES_FRED = ("DGASUSGULF", "DDFUELUSGULF", "DCOILWTICO")

COLUMNAS_MEM = ["fecha", "combustible", "precio_promedio", "modalidad", "fuente_pdf"]
COLUMNAS_MEM_REFERENCIA = [
    "semana_inicio", "combustible", "modalidad", "region", "precio_q_galon", "fuente_url",
]
# Una tabla de "últimas semanas" tiene 7 fechas; las comparaciones simples tienen 2 y mezclan
# modalidades, así que solo se aceptan tablas con al menos este número de fechas.
MIN_FECHAS_HISTORICO = 5

_FECHA = r"\d{1,2}/\d{1,2}/\d{4}"
_PRECIO = r"-?Q?\d{2}\.\d{2}"
_ETIQUETAS = {"superior": "super", "regular": "regular", "diesel": "diesel"}


def semana_inicio(fecha) -> date:
    """Martes de la semana martes-lunes (contrato 5.4: fecha - ((dow - 3 + 7) % 7), dow 1=dom)."""
    if isinstance(fecha, datetime):
        fecha = fecha.date()
    # weekday(): lunes=0 ... martes=1 ... domingo=6  ->  días desde el martes anterior
    return fecha - timedelta(days=(fecha.weekday() - 1) % 7)


def _a_fecha(txt: str) -> date:
    return datetime.strptime(txt, "%d/%m/%Y").date()


def _a_precio(txt: str) -> float:
    return float(txt.replace("Q", ""))


def _combustible(linea: str) -> str | None:
    m = re.match(r"\s*(?:gasolina\s+|combustible\s+)?(superior|regular|diesel)\b", linea, re.I)
    return _ETIQUETAS[m.group(1).lower()] if m else None


def parsear_texto_mem(texto: str, fuente_pdf: str = "") -> pd.DataFrame:
    """Extrae la(s) tabla(s) de últimas semanas de un texto ya extraído de un informe.

    Reconoce un encabezado `Producto d/m/aaaa d/m/aaaa ...` (o el que trae las fechas en la
    línea siguiente) seguido de filas Superior / Regular / Diesel, con o sin `Q`, con la etiqueta
    y los valores en la misma línea o en líneas consecutivas. Las tablas con menos de
    `MIN_FECHAS_HISTORICO` fechas se ignoran.
    """
    lineas = [ln.strip() for ln in texto.splitlines()]
    filas: list[dict] = []
    i = 0
    while i < len(lineas):
        fechas = re.findall(_FECHA, lineas[i])
        if len(fechas) < MIN_FECHAS_HISTORICO:
            i += 1
            continue
        try:
            fechas_d = [_a_fecha(f) for f in fechas]
        except ValueError:
            i += 1
            continue
        # Una tabla de últimas semanas va en orden cronológico; filas como la comparación entre
        # países (fechas desordenadas) no son una serie y se ignoran.
        if any(b <= a for a, b in zip(fechas_d, fechas_d[1:])):
            i += 1
            continue
        j, vistos, etiqueta = i + 1, set(), None
        while j < len(lineas) and len(vistos) < 3:
            linea = lineas[j]
            comb = _combustible(linea)
            precios = re.findall(_PRECIO, linea)
            if comb and len(precios) >= len(fechas_d):
                etiqueta, valores = comb, precios[-len(fechas_d):]
            elif comb and not precios:
                # etiqueta sola: los valores vienen en la línea siguiente
                etiqueta, valores = comb, None
            elif etiqueta and not comb and len(precios) == len(fechas_d):
                valores = precios
            else:
                if not comb and not precios and re.match(r"(?i)fuente|unidad", linea):
                    break
                j += 1
                continue
            if valores is not None and etiqueta and etiqueta not in vistos:
                for f, v in zip(fechas_d, valores):
                    filas.append({
                        "fecha": f, "combustible": etiqueta, "precio_promedio": _a_precio(v),
                        "modalidad": "autoservicio", "fuente_pdf": fuente_pdf,
                    })
                vistos.add(etiqueta)
                etiqueta = None
            j += 1
        i = j
    return pd.DataFrame(filas, columns=COLUMNAS_MEM)


def parsear_informe_mem(ruta_pdf) -> pd.DataFrame:
    """Parsea un informe semanal del MEM (PDF con texto). Si el PDF es una imagen, devuelve vacío
    y avisa con un warning (esas tablas se transcriben a mano)."""
    import pdfplumber  # import perezoso: solo hace falta para leer PDFs

    ruta_pdf = Path(ruta_pdf)
    partes = []
    try:
        with pdfplumber.open(ruta_pdf) as pdf:
            for pagina in pdf.pages:
                partes.append(pagina.extract_text() or "")
    except Exception as exc:  # PDF dañado: no detiene la consolidación
        log.warning("No se pudo leer %s: %s", ruta_pdf.name, exc)
        return pd.DataFrame(columns=COLUMNAS_MEM)
    df = parsear_texto_mem("\n".join(partes), ruta_pdf.name)
    if df.empty:
        log.warning("%s: sin tabla de últimas semanas con texto (¿PDF de imagen?)", ruta_pdf.name)
    return df


def _ganador_por_mayoria(grupo: pd.DataFrame, tolerancia: float):
    """De varias lecturas de la misma fecha y combustible, devuelve la fila ganadora o None.

    Las lecturas que difieren en <= `tolerancia` Q se agrupan (diferencias de redondeo). Gana el
    grupo respaldado por al menos el doble de informes que el segundo; si no hay mayoría clara
    devuelve None (hueco). Dentro del grupo ganador se usa la lectura del informe más reciente.
    """
    g = grupo.sort_values("precio_promedio")
    grupos, actual = [], [g.iloc[0]]
    for _, fila in list(g.iterrows())[1:]:
        if fila["precio_promedio"] - actual[-1]["precio_promedio"] <= tolerancia:
            actual.append(fila)
        else:
            grupos.append(actual)
            actual = [fila]
    grupos.append(actual)
    if len(grupos) == 1:
        elegido = grupos[0]
    else:
        grupos.sort(key=lambda x: len({f["fuente_pdf"] for f in x}), reverse=True)
        n1 = len({f["fuente_pdf"] for f in grupos[0]})
        n2 = len({f["fuente_pdf"] for f in grupos[1]})
        if n1 < 2 * n2:
            return None
        elegido = grupos[0]
    return max(elegido, key=lambda f: (f["_ultima"], f["fuente_pdf"]))


def consolidar_mem(dfs, excluir_conflictos: bool = False, tolerancia: float = 0.02) -> pd.DataFrame:
    """Une los resultados de varios informes (una fila por fecha, combustible y modalidad).

    Si dos informes dan lo mismo (diferencia <= `tolerancia`) gana el más reciente (el de fecha de
    monitoreo más tardía; desempata el nombre del archivo). Si discrepan:
      - `excluir_conflictos=False`: gana el informe más reciente.
      - `excluir_conflictos=True`: gana la lectura respaldada por al menos el doble de informes que
        la alternativa; sin mayoría clara se descarta (es preferible un hueco a un dato dudoso).
    Los conflictos se listan con `conflictos_mem`."""
    dfs = [d for d in dfs if d is not None and not d.empty]
    if not dfs:
        return pd.DataFrame(columns=COLUMNAS_MEM)
    todo = pd.concat(dfs, ignore_index=True)
    todo["_ultima"] = todo.groupby("fuente_pdf")["fecha"].transform("max")
    llaves = ["fecha", "combustible", "modalidad"]
    if excluir_conflictos:
        elegidas = []
        for _, grupo in todo.groupby(llaves):
            fila = _ganador_por_mayoria(grupo, tolerancia)
            if fila is not None:
                elegidas.append(fila)
        out = pd.DataFrame(elegidas)
    else:
        out = todo.sort_values(["_ultima", "fuente_pdf"]).drop_duplicates(llaves, keep="last")
    if out.empty:
        return pd.DataFrame(columns=COLUMNAS_MEM)
    return out.sort_values(["fecha", "combustible"]).reset_index(drop=True)[COLUMNAS_MEM]


def conflictos_mem(dfs, tolerancia: float = 0.02) -> pd.DataFrame:
    """Fechas/combustibles en los que dos informes dan precios distintos (para revisar a mano)."""
    dfs = [d for d in dfs if d is not None and not d.empty]
    if not dfs:
        return pd.DataFrame(columns=COLUMNAS_MEM)
    todo = pd.concat(dfs, ignore_index=True)
    g = todo.groupby(["fecha", "combustible", "modalidad"])["precio_promedio"]
    malos = g.transform(lambda s: s.max() - s.min() > tolerancia)
    return todo[malos].sort_values(["fecha", "combustible", "fuente_pdf"]).reset_index(drop=True)


def a_semanal(
    df: pd.DataFrame, region: str = "Ciudad de Guatemala", fuente_urls=None
) -> pd.DataFrame:
    """Pasa observaciones por fecha de monitoreo a una fila por semana martes-lunes.

    Si una semana tiene varios monitoreos se promedian (el promedio se redondea a 2 decimales).
    `fuente_urls` es un dict {nombre_del_pdf: url}; la columna `fuente_url` junta las URL de los
    informes que aportaron datos a esa semana.
    """
    if df.empty:
        return pd.DataFrame(columns=COLUMNAS_MEM_REFERENCIA)
    fuente_urls = fuente_urls or {}
    d = df.copy()
    d["semana_inicio"] = d["fecha"].map(semana_inicio)
    d["fuente_url"] = d["fuente_pdf"].map(lambda p: fuente_urls.get(p, p))
    sal = (
        d.groupby(["semana_inicio", "combustible", "modalidad"], as_index=False)
        .agg(precio_q_galon=("precio_promedio", lambda s: round(float(s.mean()), 2)),
             fuente_url=("fuente_url", lambda s: " | ".join(sorted(set(s)))))
    )
    sal["region"] = region
    sal = sal.sort_values(["semana_inicio", "combustible"]).reset_index(drop=True)
    return sal[COLUMNAS_MEM_REFERENCIA]


def semanas_faltantes(semanal: pd.DataFrame, desde: date, hasta: date) -> pd.DataFrame:
    """Combustible y semana (martes) sin dato en el rango [desde, hasta]."""
    inicio, esperado = semana_inicio(desde), []
    while inicio <= hasta:
        esperado.append(inicio)
        inicio += timedelta(days=7)
    tiene = set()
    if not semanal.empty:
        tiene = set(zip(semanal["semana_inicio"], semanal["combustible"]))
    combustibles = ("super", "regular", "diesel")
    faltan = [(s, c) for s in esperado for c in combustibles if (s, c) not in tiene]
    return pd.DataFrame(faltan, columns=["semana_inicio", "combustible"])


def descargar_fred(serie: str, destino) -> Path:
    """Descarga el CSV de una serie de FRED a `destino` (archivo o carpeta) y devuelve la ruta."""
    import requests

    destino = Path(destino)
    if destino.is_dir():
        destino = destino / f"{serie}.csv"
    destino.parent.mkdir(parents=True, exist_ok=True)
    r = requests.get(URL_FRED.format(serie=serie), timeout=60)
    r.raise_for_status()
    destino.write_bytes(r.content)
    return destino


def leer_fred(ruta_csv) -> pd.DataFrame:
    """Lee un CSV de FRED -> DataFrame (fecha, serie, valor). "." y vacíos pasan a NaN."""
    crudo = pd.read_csv(ruta_csv, na_values=[".", ""])
    col_fecha, col_valor = crudo.columns[0], crudo.columns[1]
    return pd.DataFrame({
        "fecha": pd.to_datetime(crudo[col_fecha]).dt.date,
        "serie": col_valor,
        "valor": pd.to_numeric(crudo[col_valor], errors="coerce"),
    })
