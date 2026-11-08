# Build from the repository root so the shared web UI (public/) is included:
#   docker build -f backend/Dockerfile .
FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .
COPY public/ /public/

# Run as an unprivileged user
RUN useradd --create-home --uid 10001 yaxin && chown -R yaxin /app
USER yaxin

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
