"""Genera los tres PDF de entrega desde fuentes y evidencias locales del proyecto."""

from __future__ import annotations

import html
import json
import re
from pathlib import Path

import qrcode
from reportlab.graphics import renderPDF
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.shapes import Drawing, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

RAIZ = Path(__file__).resolve().parents[1]
SALIDA = RAIZ / "output/pdf"
PRIVADO = RAIZ / "artifacts/entregables"
EVIDENCIA = RAIZ / "docs/evidencias_job.json"
AZUL = colors.HexColor("#17324D")
VERDE = colors.HexColor("#087F8C")
GRIS = colors.HexColor("#536372")
EQUIPO = "Alina Carias, Marcos Diaz, Daniel Machic, Ignacio Mendez, Ariela Mishaan y Diego Soto"
API = "http://159.65.111.14:8000"


def evidencia():
    return json.loads(EVIDENCIA.read_text(encoding="utf-8")) if EVIDENCIA.exists() else {}


def texto_job():
    runs = evidencia().get("runs", [])
    if len(runs) != 2:
        return "Las dos ejecuciones completas permanecen en validación."
    texto = "Las dos ejecuciones terminaron correctamente. "
    for numero, run in enumerate(runs, 1):
        duraciones = ", ".join(
            f"{t['task_key']} {t.get('execution_duration', 0) / 1000:.0f} s" for t in run["tareas"]
        )
        texto += f"Corrida {numero}, ID {run['run_id']}: {run['fotos']} fotos, {duraciones}. "
    return texto + "El número de rutas distintas coincide con el de fotos en ambas cargas."


def estilo(nombre, tamano, interlineado=None, **kwargs):
    opciones = {
        "fontName": "Arial",
        "fontSize": tamano,
        "leading": interlineado or tamano * 1.38,
        "textColor": AZUL,
        "spaceAfter": 9,
        "alignment": TA_LEFT,
    }
    opciones.update(kwargs)
    return ParagraphStyle(nombre, **opciones)


def seguro(texto):
    return html.escape(str(texto))


def pie(c, doc):
    c.setFont("Arial", 8)
    c.setFillColor(GRIS)
    c.drawString(46, 25, "Equipo 06  -  ML Engineering  -  15 noviembre 2026")
    c.drawRightString(A4[0] - 46, 25, str(doc.page))


def tabla_pdf(filas, ancho):
    columnas = len(filas[0])
    celda = estilo("celda", 9, 12)
    datos = [[Paragraph(seguro(v), celda) for v in f] for f in filas]
    tabla = Table(datos, colWidths=[ancho / columnas] * columnas, repeatRows=1)
    tabla.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8F0F3")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LINEBELOW", (0, 0), (-1, 0), 0.7, VERDE),
                ("LINEBELOW", (0, 1), (-1, -1), 0.3, colors.HexColor("#D7E0E5")),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return tabla


def informe():
    fuente = (RAIZ / "docs/informe.md").read_text(encoding="utf-8")
    fuente = fuente.replace("{{EVIDENCIA_JOB}}", texto_job())
    contenido = []
    cuerpo = estilo("cuerpo", 10, 13.9)
    titulo = estilo("titulo", 21, 25, fontName="ArialBold")
    seccion = estilo("seccion", 13, 17, fontName="ArialBold", spaceBefore=8)
    parrafos = fuente.split("\n\n")
    ancho = A4[0] - 92
    for bloque in parrafos:
        bloque = bloque.strip()
        if not bloque:
            continue
        if bloque == "<!-- pagebreak -->":
            contenido.append(PageBreak())
        elif bloque.startswith("!["):
            ruta = re.search(r"\((.+)\)", bloque).group(1)
            contenido.append(Image(str(RAIZ / "docs" / ruta), width=450, height=300))
            contenido.append(Spacer(1, 8))
        elif bloque.startswith("|"):
            filas = [
                [s.strip() for s in linea.strip("|").split("|")]
                for linea in bloque.splitlines()
                if "---" not in linea
            ]
            contenido.append(tabla_pdf(filas, ancho))
            contenido.append(Spacer(1, 10))
        elif bloque.startswith("## "):
            contenido.append(Paragraph(seguro(bloque[3:]), seccion))
        elif bloque.startswith("# "):
            contenido.append(Paragraph(seguro(bloque[2:]), titulo))
        else:
            contenido.append(Paragraph(seguro(bloque.replace("\n", " ")), cuerpo))
    doc = SimpleDocTemplate(
        str(SALIDA / "informe.pdf"),
        pagesize=A4,
        rightMargin=46,
        leftMargin=46,
        topMargin=38,
        bottomMargin=42,
        title="Informe técnico del Equipo 06",
        author=EQUIPO,
    )
    doc.build(contenido, onFirstPage=pie, onLaterPages=pie)


def parrafo(c, texto, x, y, ancho, tamano=21, color=AZUL, negrita=False):
    s = estilo(
        "slide", tamano, tamano * 1.3, fontName="ArialBold" if negrita else "Arial", textColor=color
    )
    p = Paragraph(seguro(texto).replace("\n", "<br/>"), s)
    _, alto = p.wrap(ancho, 1000)
    p.drawOn(c, x, y - alto)
    return y - alto - 18


def grafico(c, categorias, series, nombres, x, y, ancho=800, alto=290, maximo=100):
    dibujo = Drawing(ancho, alto)
    chart = VerticalBarChart()
    chart.x, chart.y = 45, 45
    chart.width, chart.height = ancho - 70, alto - 75
    chart.data = series
    chart.categoryAxis.categoryNames = categorias
    chart.categoryAxis.labels.fontName = "Arial"
    chart.categoryAxis.labels.fontSize = 14
    chart.valueAxis.valueMin, chart.valueAxis.valueMax = 0, maximo
    chart.valueAxis.valueStep = 20 if maximo == 100 else 0.2
    chart.valueAxis.labels.fontName = "Arial"
    chart.valueAxis.labels.fontSize = 12
    chart.bars[0].fillColor = VERDE
    if len(series) > 1:
        chart.bars[1].fillColor = AZUL
    dibujo.add(chart)
    for i, nombre in enumerate(nombres):
        dibujo.add(
            String(
                48 + i * 220,
                alto - 5,
                nombre,
                fontName="ArialBold",
                fontSize=14,
                fillColor=VERDE if i == 0 else AZUL,
            )
        )
    renderPDF.draw(dibujo, c, x, y)


def diapositivas():
    c = canvas.Canvas(str(SALIDA / "presentacion_jurado.pdf"), pagesize=(960, 540))
    c.setTitle("Precios de combustible en Guatemala - Equipo 06")
    c.setAuthor(EQUIPO)
    guion = []

    def nueva(titulo, notas):
        if guion:
            c.showPage()
        c.setFillColor(colors.white)
        c.rect(0, 0, 960, 540, fill=1, stroke=0)
        parrafo(c, titulo, 44, 500, 870, 32, negrita=True)
        c.setFont("Arial", 10)
        c.setFillColor(GRIS)
        c.drawRightString(916, 20, f"Equipo 06    {len(guion) + 1}")
        guion.append((titulo, notas))

    nueva("Precios de combustible en Guatemala", "Alina presenta el problema. Duración 1 minuto.")
    parrafo(c, "Fotos, datos y predicción semanal", 44, 363, 800, 29)
    parrafo(c, EQUIPO, 44, 235, 820, 20)
    parrafo(c, "Proyecto final de ML Engineering\n15 de noviembre de 2026", 44, 130, 820, 18)

    nueva("Arquitectura del proyecto", "Marcos explica las capas y el consumo de Oro. 1 minuto.")
    c.drawImage(str(RAIZ / "docs/arquitectura.png"), 35, 46, width=600, height=400)
    parrafo(c, "Bronce conserva las fotos originales.", 658, 410, 255, 20)
    parrafo(c, "Plata extrae y valida precios.", 658, 295, 255, 20)
    parrafo(c, "Oro organiza semanas y registra predicciones.", 658, 190, 255, 20)

    nueva(
        "Fotos y referencias de evaluación",
        "Daniel describe el conjunto y la verdad manual. 1 minuto.",
    )
    parrafo(c, "38 fotos oficiales en Bronce", 44, 395, 850, 29, negrita=True)
    parrafo(c, "36 fotos etiquetadas y 85 precios legibles", 44, 300, 850, 26)
    parrafo(c, "La evaluación exige una diferencia menor que Q0.005.", 44, 195, 850, 22)
    parrafo(c, "Combustibles incluidos: súper, regular y diésel.", 44, 118, 850, 22)

    nueva(
        "Calidad de extracción OCR",
        "Daniel compara las variantes. 1 minuto. Fuente: CSV comparativa_ocr.",
    )
    grafico(
        c,
        ["Original", "CLAHE", "CLAHE x2", "Binarizado"],
        [[88.2, 91.8, 90.6, 51.8]],
        ["Precios correctos (%)"],
        40,
        118,
    )
    parrafo(c, "RapidOCR con gris_clahe acertó 78 de los 85 precios.", 44, 100, 850, 21)

    nueva("Validación de los precios", "Daniel muestra los errores y explica cuarentena. 1 minuto.")
    parrafo(c, "93 registros aceptados y 3 rechazados", 44, 400, 850, 29, negrita=True)
    parrafo(c, "Dos fotos sin precios legibles y una lectura con baja confianza.", 44, 305, 850, 23)
    parrafo(c, "Ejemplo: regular Q35.16 se leyó como Q35.76.", 44, 210, 850, 23)
    parrafo(c, "Las reglas controlan rango, combustible, fecha y confianza.", 44, 115, 850, 22)

    nueva(
        "Predicción de la dirección semanal",
        "Ignacio explica variables, objetivo y validación. 1 minuto.",
    )
    parrafo(c, "El objetivo clasifica sube, baja o se_mantiene.", 44, 400, 850, 27)
    parrafo(c, "Variaciones recientes, promedio de cuatro semanas y combustible.", 44, 310, 850, 23)
    parrafo(c, "WTI y subsidio cuando hay información disponible.", 44, 225, 850, 23)
    parrafo(
        c, "183 registros de entrenamiento y 30 de prueba, separados por semana.", 44, 130, 850, 23
    )

    nueva(
        "Modelo frente a la línea base",
        "Ignacio interpreta ambas métricas. 1 minuto. Fuente: metricas_modelo.",
    )
    grafico(
        c,
        ["Línea base", "Logística", "Árbol"],
        [[0.5, 0.6, 0.4333], [0.2564, 0.313, 0.3056]],
        ["Accuracy", "F1 macro"],
        40,
        118,
        maximo=1,
    )
    parrafo(c, "La logística obtuvo 60% de accuracy y F1 macro de 0.313.", 44, 105, 850, 21)
    parrafo(c, "La clase se_mantiene requiere mejorar su cobertura.", 44, 65, 850, 18)

    nueva("Job y evidencia de ejecución", "Ariela explica orquestación y alertas. 1 minuto.")
    parrafo(c, "Tres tareas encadenadas: Bronce, Plata y Oro.", 44, 400, 850, 26)
    parrafo(c, "Serverless con entorno fijado y alertas de fallo por correo.", 44, 315, 850, 22)
    runs = evidencia().get("runs", [])
    mensaje = (
        "Dos ejecuciones exitosas: una foto en la primera carga y dos en la segunda."
        if len(runs) == 2
        else "Dos cargas incrementales en validación."
    )
    parrafo(c, mensaje, 44, 225, 850, 24, negrita=True)
    parrafo(c, "La validación utiliza esquemas aislados del equipo.", 44, 120, 850, 21)

    nueva(
        "Demostración de la API",
        "Ariela realiza la demo. Comprobar /health desde un teléfono antes del jurado.",
    )
    y = 400
    for t in ["/health", "/precios/actual", "/precios", "/prediccion", "/modelo/metricas"]:
        y = parrafo(c, t, 44, y, 580, 24)
    c.drawImage(str(PRIVADO / "qr_api.png"), 700, 185, 170, 170)
    parrafo(c, API, 630, 145, 290, 16)
    parrafo(c, "API pública con datos de Oro (fuente_oro=databricks).", 44, 65, 850, 18)

    nueva(
        "Alcance y próximos pasos",
        "Diego explica límites y cierre. 1 minuto. Demo y preguntas después.",
    )
    parrafo(c, "El histórico termina el 3 de noviembre de 2026.", 44, 400, 850, 24)
    parrafo(c, "Las predicciones disponibles corresponden al 10 de noviembre.", 44, 315, 850, 24)
    parrafo(
        c, "La infraestructura actual usa tablas gestionadas y lectura por SQL.", 44, 225, 850, 23
    )
    parrafo(
        c,
        "Más historia y mejor cobertura de las clases permitirán evaluar nuevas mejoras.",
        44,
        130,
        850,
        23,
    )
    c.save()
    texto = "# Guion del jurado\n\nReparto sugerido, ajustable por el equipo.\n\n"
    for n, (titulo, notas) in enumerate(guion, 1):
        texto += f"## {n}. {titulo}\n\n{notas}\n\n"
    texto += "La exposición dura 10 minutos. Reservar 5 para demo y 5 para preguntas.\n"
    texto += "Fuentes: informe.md, evidencias_job.md y los artefactos de MLflow del equipo.\n"
    (RAIZ / "presentacion/guion_jurado.md").write_text(texto, encoding="utf-8")


def resumen():
    estilos = getSampleStyleSheet()
    estilos.add(estilo("resumen", 10, 14))
    estilos.add(estilo("encabezado", 21, 25, fontName="ArialBold"))
    story = [Paragraph("Precios de combustible en Guatemala", estilos["encabezado"])]
    for t in [
        "Equipo 06. Proyecto final de ML Engineering, CC3105.",
        EQUIPO,
        "El proyecto extrae precios de fotos y clasifica la dirección del precio de súper, "
        "regular y diésel para la semana posterior al último dato disponible.",
        "Bronce conserva las fotos. Plata aplica OCR y reglas de calidad. Oro organiza las "
        "semanas y registra indicadores, métricas y predicciones.",
    ]:
        story.append(Paragraph(seguro(t), estilos["resumen"]))
    story.append(
        tabla_pdf(
            [
                ["Resultado", "Evidencia"],
                ["Extracción OCR", "91.8% de acierto en 85 precios de 36 fotos"],
                ["Modelo elegido", "Regresión logística, accuracy 60%, F1 macro 0.313"],
                ["Línea base", "Accuracy 50%, F1 macro 0.2564"],
                ["Prueba del modelo", "30 registros de diez semanas, con separación temporal"],
            ],
            A4[0] - 92,
        )
    )
    story.append(Spacer(1, 12))
    for t in [
        texto_job(),
        "La predicción disponible corresponde al 10 de noviembre de 2026 porque el "
        "histórico termina el 3. La estabilidad del precio es la clase con menor cobertura.",
        "La demo incluye el Job y las consultas de precio actual, predicción y métricas.",
        "API pública: " + API + " (documentación en /docs).",
    ]:
        story.append(Paragraph(seguro(t), estilos["resumen"]))
    story.append(Image(str(PRIVADO / "qr_api.png"), width=88, height=88, hAlign="LEFT"))
    doc = SimpleDocTemplate(
        str(SALIDA / "resumen_jurado.pdf"),
        pagesize=A4,
        rightMargin=46,
        leftMargin=46,
        topMargin=38,
        bottomMargin=42,
    )
    doc.build(story, onFirstPage=pie, onLaterPages=pie)


def main():
    SALIDA.mkdir(parents=True, exist_ok=True)
    PRIVADO.mkdir(parents=True, exist_ok=True)
    for normal, negrita in [
        ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf"),
        ("/System/Library/Fonts/Supplemental/Arial.ttf",
         "/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
    ]:
        if Path(normal).exists() and Path(negrita).exists():
            break
    pdfmetrics.registerFont(TTFont("Arial", normal))
    pdfmetrics.registerFont(TTFont("ArialBold", negrita))
    qrcode.make(API).save(PRIVADO / "qr_api.png")
    informe()
    diapositivas()
    resumen()
    print("PDF generados en", SALIDA)


if __name__ == "__main__":
    main()
