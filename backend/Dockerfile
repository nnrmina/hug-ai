# Build from the repo root so the web app in public/ is included:
#   docker build -f backend/Dockerfile -t hug-ai .
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PUBLIC_DIR=/srv/public \
    DATABASE_URL=sqlite:////data/hug.db \
    TTS_CACHE_DIR=/data/tts_cache

WORKDIR /srv

COPY backend/requirements.txt backend/requirements.txt
RUN pip install -r backend/requirements.txt

COPY backend/ backend/
COPY public/ public/

# Unprivileged runtime user; /data is the persistent volume (SQLite + voice cache)
RUN useradd --system --uid 10001 --home /srv hug \
    && mkdir -p /data/tts_cache \
    && chown -R hug:hug /data
USER hug
VOLUME ["/data"]

WORKDIR /srv/backend
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4).status == 200 else 1)"

# One worker on purpose: conversation memory and pending confirmations live in process memory.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--proxy-headers", "--forwarded-allow-ips", "*"]
