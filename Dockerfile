# syntax=docker/dockerfile:1
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    TZ=Australia/Sydney

# tzdata for correct AEST labels + libfreetype/matplotlib runtime deps
RUN apt-get update \
    && apt-get install -y --no-install-recommends tzdata fontconfig libfreetype6 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY render.py webhook.py app.py ./

# non-root runtime user
RUN useradd -m -u 10001 appuser \
    && mkdir -p /data \
    && chown appuser:appuser /data /app
USER appuser

ENV CHART_OUT=/data/tarkov_au_isp_latency.png \
    STATE_DIR=/data \
    REFRESH_INTERVAL=1800

VOLUME ["/data"]

HEALTHCHECK --interval=5m --timeout=15s --start-period=30s --retries=3 \
    CMD python app.py --health || exit 1

ENTRYPOINT ["python", "app.py"]
CMD []
