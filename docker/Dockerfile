FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HOME=/tmp

# Librerías de sistema que necesita OpenCV (dependencia de RapidOCR)
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Paquete + extra [api] (SIN easyocr: es pesado y no se usa en producción)
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install ".[api]"

COPY config ./config
COPY artifacts_demo ./artifacts_demo

# Usuario no root
RUN useradd --uid 1000 --create-home app \
    && mkdir -p /app/artifacts /app/logs \
    && chown -R app:app /app/artifacts /app/logs
USER app

ENV ARTIFACTS_DIR=/app/artifacts \
    ARTIFACTS_DEMO_DIR=/app/artifacts_demo \
    LOGS_DIR=/app/logs \
    GASOLINA_CONFIG=/app/config/config.yaml

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=4)" || exit 1

CMD ["gasolina-api"]
