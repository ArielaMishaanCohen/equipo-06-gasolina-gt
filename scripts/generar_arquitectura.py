"""Genera docs/arquitectura.drawio (editable en app.diagrams.net) y docs/arquitectura.png
desde una sola definición de cajas y flechas.

    python scripts/generar_arquitectura.py

Para cambiar el diagrama se edita NODOS / FLECHAS aquí y se vuelve a correr (así el .drawio y el
.png nunca se desincronizan). Solo usa Pillow, que ya es dependencia del paquete.
"""

from __future__ import annotations

import math
from pathlib import Path
from xml.sax.saxutils import escape

from PIL import Image, ImageDraw, ImageFont

RAIZ = Path(__file__).resolve().parents[1]
ANCHO, ALTO = 1770, 1180

# Paleta (relleno, borde)
C = {
    "s3": ("#fff8ec", "#d98c1f"),
    "raw": ("#eeeeee", "#777777"),
    "bronce": ("#f3d9c0", "#a0612a"),
    "plata": ("#e6e9ee", "#7d8794"),
    "oro": ("#fbecb0", "#b38b00"),
    "dbx": ("#fff0ec", "#e0442a"),
    "job": ("#ffffff", "#e0442a"),
    "tarea": ("#ffe1d9", "#e0442a"),
    "aux": ("#ffffff", "#b5776b"),
    "droplet": ("#eaf3ff", "#1f6fd1"),
    "api": ("#ffffff", "#1f6fd1"),
    "actor": ("#ffffff", "#333333"),
    "gh": ("#f2f2f2", "#24292f"),
    "ext": ("#f4fbf2", "#3d8a34"),
}

# id: (texto, x, y, ancho, alto, estilo, es_contenedor)
NODOS = {
    # Contenedores
    "aws": ("AWS S3 · un bucket por capa (external locations de Unity Catalog)",
            300, 30, 1370, 250, "s3", True),
    "dbx": ("Databricks (workspace del curso)", 300, 330, 1370, 400, "dbx", True),
    "job": ("Job equipo-06-pipeline · job cluster · trigger por archivo nuevo · correo si falla",
            330, 375, 1010, 215, "job", True),
    "droplet": ("Droplet DigitalOcean · 159.65.111.14 · usuario sin sudo",
                300, 790, 1370, 360, "droplet", True),
    # S3
    "raw": ("FOTOS (xloc-raw)\ncc3105-raw…/img/\n.HEIC con EXIF · solo lectura", 330, 85, 290, 150,
            "raw", False),
    "bronce": ("BRONCE (xloc-cusn)\ncc3105-cusn…/equipo6/\nfotos_precios · mem_referencia_raw",
               660, 85, 300, 150, "bronce", False),
    "plata": ("PLATA (xloc-ag)\ncc3105-ag…/equipo6/\nprecios · precios_rejected · mem",
              1000, 85, 300, 150, "plata", False),
    "oro": ("ORO (xloc-au)\ncc3105-au…/equipo6/gold/\nprecio_semanal · variacion_semanal\n"
            "features_modelo · predicciones\nmetricas_modelo", 1340, 85, 300, 165, "oro", False),
    # Databricks
    "t1": ("01_bronze\nbinaryFile / Auto Loader\nincremental · _ingestion_timestamp",
           360, 400, 290, 125, "tarea", False),
    "t2": ("02_silver\nOCR (paquete gasolina) + reglas\ncuarentena · MERGE idempotente",
           700, 400, 290, 125, "tarea", False),
    "t3": ("03_gold\nsemana martes-lunes · variación\nfeatures · modelo · predicciones",
           1040, 400, 280, 125, "tarea", False),
    "mlflow": ("MLflow\nexperimentos OCR y\nclasificador vs. línea base", 1375, 375, 270, 120,
               "aux", False),
    "interactivo": ("Cluster interactivo\ndesarrollo · autoterminación ≤ 30 min", 1375, 520,
                    270, 95, "aux", False),
    "gitfolder": ("Git folder (repo sincronizado)\nnotebooks de pipelines/", 330, 610, 420, 80,
                  "aux", False),
    # Droplet
    "api": ("API FastAPI (uv + pyproject.toml + uv.lock)\n"
            "puerto 8006 · nohup + @reboot · .env (600)\n"
            "oro.py: lee Delta de S3 con credenciales de solo lectura\n(caché 5 min; tablas demo "
            "como respaldo)", 1010, 845, 640, 140, "api", False),
    "endpoints": ("GET /health · /precios/actual · /precios?combustible&desde&hasta&limit\n"
                  "/prediccion · /modelo/metricas · /docs (Swagger) · página web (QR)",
                  1010, 1010, 640, 110, "api", False),
    "logs": ("logs/*.jsonl\n(cron fin_de_clase.sh)", 640, 865, 270, 100, "api", False),
    # Actores
    "profe": ("Catedrático\nsube fotos semanales", 30, 100, 220, 90, "actor", False),
    "mem": ("MEM (histórico de\nprecios de referencia)", 30, 215, 220, 80, "ext", False),
    "equipo": ("Equipo 6\n(Mac + Claude Code)", 30, 560, 220, 90, "actor", False),
    "github": ("GitHub\nequipo-06-gasolina-gt\nActions: ruff + pytest +\nimagen GHCR · deploy",
               30, 740, 220, 130, "gh", False),
    "usuario": ("Jurado / usuario\nnavegador o teléfono", 30, 1020, 220, 90, "actor", False),
}

# Contenedores cuyo título va abajo (para que las flechas no lo crucen): "bl" | "br"
TITULO_ABAJO = {"job": "bl", "dbx": "br"}

# (origen, destino, texto, punteada[, puntos intermedios])
FLECHAS = [
    ("profe", "raw", "sube .HEIC", False),
    ("mem", "bronce", "CSV / PDF", True, [(700, 258)]),
    ("raw", "t1", "lee", False),
    ("t1", "bronce", "escribe", False),
    ("t1", "t2", "", False),
    ("t2", "t3", "", False),
    ("bronce", "t2", "lee", False),
    ("t2", "plata", "escribe", False),
    ("plata", "t3", "lee", False),
    ("t3", "oro", "escribe", False),
    ("job", "mlflow", "registra", True),
    ("oro", "api", "solo lectura", False, [(1700, 200), (1700, 900)]),
    ("api", "endpoints", "", False),
    ("api", "logs", "", True),
    ("equipo", "gitfolder", "git push / pull", False),
    ("equipo", "github", "git push", False),
    ("github", "droplet", "deploy por SSH", False),
    ("equipo", "droplet", "SSH", True),
    ("usuario", "endpoints", "HTTP", False),
]


# --------------------------------------------------------------------------------------------
def _centro(n):
    _, x, y, w, h, *_ = NODOS[n]
    return x + w / 2, y + h / 2


def _borde(n, hacia):
    """Punto del borde de la caja n en la dirección del punto `hacia`."""
    _, x, y, w, h, *_ = NODOS[n]
    cx, cy = x + w / 2, y + h / 2
    dx, dy = hacia[0] - cx, hacia[1] - cy
    if dx == 0 and dy == 0:
        return cx, cy
    t = min((w / 2) / abs(dx) if dx else math.inf, (h / 2) / abs(dy) if dy else math.inf)
    return cx + dx * t, cy + dy * t


def generar_drawio(ruta: Path) -> None:
    celdas = ['<mxCell id="0"/>', '<mxCell id="1" parent="0"/>']
    for nid, (texto, x, y, w, h, est, cont) in NODOS.items():
        relleno, borde = C[est]
        estilo = (f"rounded=1;whiteSpace=wrap;html=1;fillColor={relleno};strokeColor={borde};"
                  f"fontSize={13 if cont else 12};arcSize={4 if cont else 10};")
        if cont:
            pos = TITULO_ABAJO.get(nid)
            estilo += ("verticalAlign=bottom;spacingBottom=6;" if pos else
                       "verticalAlign=top;spacingTop=6;") + "fontStyle=1;"
            estilo += ("align=right;spacingRight=10;" if pos == "br"
                       else "align=left;spacingLeft=10;")
        valor = escape(texto).replace("\n", "&lt;br&gt;")
        celdas.append(f'<mxCell id="{nid}" value="{valor}" style="{estilo}" vertex="1" '
                      f'parent="1"><mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" '
                      f'as="geometry"/></mxCell>')
    for i, (a, b, texto, punteada, *resto) in enumerate(FLECHAS):
        puntos = resto[0] if resto else []
        estilo = ("edgeStyle=none;html=1;endArrow=block;endFill=1;strokeColor=#444444;"
                  "fontSize=11;labelBackgroundColor=#ffffff;")
        if punteada:
            estilo += "dashed=1;"
        pts = "".join(f'<mxPoint x="{x}" y="{y}"/>' for x, y in puntos)
        celdas.append(f'<mxCell id="e{i}" value="{escape(texto)}" style="{estilo}" edge="1" '
                      f'parent="1" source="{a}" target="{b}">'
                      '<mxGeometry relative="1" as="geometry">'
                      + (f'<Array as="points">{pts}</Array>' if pts else "")
                      + '</mxGeometry></mxCell>')
    xml = (f'<mxfile host="generar_arquitectura.py"><diagram name="Arquitectura">'
           f'<mxGraphModel dx="{ANCHO}" dy="{ALTO}" grid="1" gridSize="10" page="1" '
           f'pageWidth="{ANCHO}" pageHeight="{ALTO}"><root>{"".join(celdas)}</root>'
           f'</mxGraphModel></diagram></mxfile>')
    ruta.write_text(xml, encoding="utf-8")


def _fuente(tam: int, negrita: bool = False):
    candidatos = (["/System/Library/Fonts/Supplemental/Arial Bold.ttf",
                   "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"] if negrita else
                  ["/System/Library/Fonts/Supplemental/Arial.ttf",
                   "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"])
    for c in candidatos:
        if Path(c).is_file():
            return ImageFont.truetype(c, tam)
    return ImageFont.load_default()


def _segmento(d, p1, p2, punteada: bool, flecha: bool, s: int) -> None:
    (x1, y1), (x2, y2) = p1, p2
    largo = math.hypot(x2 - x1, y2 - y1) or 1.0
    ux, uy = (x2 - x1) / largo, (y2 - y1) / largo
    punta = 12 * s if flecha else 0
    xf, yf = x2 - ux * punta, y2 - uy * punta
    if punteada:
        paso, i = 10 * s, 0.0
        while i < largo - punta:
            j = min(i + paso * 0.6, largo - punta)
            d.line([x1 + ux * i, y1 + uy * i, x1 + ux * j, y1 + uy * j], fill="#444444",
                   width=2 * s)
            i += paso
    else:
        d.line([x1, y1, xf, yf], fill="#444444", width=2 * s)
    if flecha:
        px, py = -uy, ux
        d.polygon([(x2, y2), (xf + px * 6 * s, yf + py * 6 * s),
                   (xf - px * 6 * s, yf - py * 6 * s)], fill="#444444")


def _posicion_etiqueta(pts, s: int) -> tuple[float, float]:
    """Mitad del segmento más largo; si la flecha cruza el hueco entre S3 y Databricks
    (y = 305), la etiqueta va ahí para no tapar títulos."""
    hueco = 305 * s
    for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
        if min(y1, y2) < hueco < max(y1, y2):
            t = (hueco - y1) / (y2 - y1)
            return x1 + (x2 - x1) * t, hueco
    (x1, y1), (x2, y2) = max(zip(pts, pts[1:]),
                             key=lambda q: math.hypot(q[1][0] - q[0][0], q[1][1] - q[0][1]))
    return (x1 + x2) / 2, (y1 + y2) / 2


def generar_png(ruta: Path, escala: int = 2) -> None:
    s = escala
    img = Image.new("RGB", (ANCHO * s, ALTO * s), "white")
    d = ImageDraw.Draw(img)
    f_cont, f_nodo, f_flecha = _fuente(15 * s, True), _fuente(13 * s), _fuente(12 * s)

    # contenedores primero, luego cajas
    for cont in (True, False):
        for nid, (texto, x, y, w, h, est, es_cont) in NODOS.items():
            if es_cont != cont:
                continue
            relleno, borde = C[est]
            d.rounded_rectangle([x * s, y * s, (x + w) * s, (y + h) * s],
                                radius=(10 if es_cont else 12) * s, fill=relleno,
                                outline=borde, width=2 * s)
            if es_cont:
                pos = TITULO_ABAJO.get(nid)
                if pos == "br":
                    d.text(((x + w - 14) * s, (y + h - 10) * s), texto, font=f_cont, fill=borde,
                           anchor="rd")
                elif pos == "bl":
                    d.text(((x + 14) * s, (y + h - 10) * s), texto, font=f_cont, fill=borde,
                           anchor="ld")
                else:
                    d.text(((x + 14) * s, (y + 10) * s), texto, font=f_cont, fill=borde)
            else:
                d.multiline_text(((x + w / 2) * s, (y + h / 2) * s), texto, font=f_nodo,
                                 fill="#1a1a1a", anchor="mm", align="center", spacing=4 * s)

    for a, b, texto, punteada, *resto in FLECHAS:
        puntos = resto[0] if resto else []
        ruta_pts = ([_borde(a, puntos[0] if puntos else _centro(b))] + list(puntos)
                    + [_borde(b, puntos[-1] if puntos else _centro(a))])
        ruta_pts = [(x * s, y * s) for x, y in ruta_pts]
        for k, (p1, p2) in enumerate(zip(ruta_pts, ruta_pts[1:])):
            ultimo = k == len(ruta_pts) - 2
            _segmento(d, p1, p2, punteada, flecha=ultimo, s=s)
        if texto:
            mx, my = _posicion_etiqueta(ruta_pts, s)
            caja = d.textbbox((mx, my), texto, font=f_flecha, anchor="mm")
            d.rectangle([caja[0] - 4 * s, caja[1] - 2 * s, caja[2] + 4 * s, caja[3] + 2 * s],
                        fill="white")
            d.text((mx, my), texto, font=f_flecha, fill="#333333", anchor="mm")

    img.save(ruta, optimize=True)


if __name__ == "__main__":
    docs = RAIZ / "docs"
    generar_drawio(docs / "arquitectura.drawio")
    generar_png(docs / "arquitectura.png")
    print(f"Listo: {docs / 'arquitectura.drawio'} y {docs / 'arquitectura.png'}")
