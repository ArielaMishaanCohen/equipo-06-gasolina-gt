# Presentación ante el jurado

- [CONTENIDO_PRESENTACION.md](CONTENIDO_PRESENTACION.md): fuente completa para rehacer
  las diapositivas; contiene texto, gráficos, notas, demo, preguntas y evidencias.
- [presentacion_jurado.pdf](presentacion_jurado.pdf): diapositivas para 10 minutos
  de exposición, seguidos de 5 de demo y 5 de preguntas.
- [resumen_jurado.pdf](resumen_jurado.pdf): una página con el problema, la arquitectura,
  los resultados y la URL de la API. Se entrega **48 horas antes** de la presentación.
- [guion_jurado.md](guion_jurado.md): guion editable y reparto sugerido.

Incluyen resultados reales de OCR, modelos y las dos ejecuciones del Job.
La API pública está en http://159.65.111.14:8000 (Swagger en `/docs`).
El QR apunta a esa dirección: comprobarlo desde un teléfono antes de exponer.

Para regenerar desde las fuentes del repositorio:

```powershell
uv pip install reportlab pypdf qrcode
.venv/Scripts/python.exe scripts/generar_entregables.py
```

La salida está en `output/pdf/`. Tras revisar las páginas, copiar el informe a
`docs/informe.pdf` y los dos PDF del jurado a esta carpeta. Las fuentes están en
`docs/informe.md`, `docs/evidencias_job.json` y `scripts/generar_entregables.py`.

Actualizar el despliegue público y el acuerdo sobre SQL frente a S3 cuando se resuelvan.
Una grabación y capturas pueden respaldar la demo; no se ha generado una grabación.
