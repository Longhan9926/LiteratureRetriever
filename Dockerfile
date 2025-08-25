# syntax=docker/dockerfile:1
FROM python:3.12-slim

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl ca-certificates && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# Create data directory for sqlite
RUN mkdir -p /data
VOLUME ["/data"]

ENV FLASK_APP=app/wsgi.py \
    SQLITE_PATH=/data/papers.db \
    SCHEDULER_CRON="*/30 * * * *" \
    MAX_ITEMS_PER_RUN=30 \
    PYTHONPATH=/app

EXPOSE 8000
CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:8000", "app.wsgi:app"]
