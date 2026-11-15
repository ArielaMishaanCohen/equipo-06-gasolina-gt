# Presentación ante el jurado

- [presentacion_jurado.pdf](presentacion_jurado.pdf): diez diapositivas.
- [resumen_jurado.pdf](resumen_jurado.pdf): una página, para entregar 48 horas antes.
- [guion_jurado.md](guion_jurado.md): guion editable y reparto sugerido.

Incluyen resultados reales de OCR, modelos y las dos ejecuciones del Job.
La API pública está pendiente de despliegue por la responsable de SSH.
El QR apunta al servidor previsto: comprobarlo antes de exponer.

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
