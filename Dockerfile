# syntax=docker/dockerfile:1
# ============================================
# Multi-stage Dockerfile for the Car Rental AI Agent API
# ============================================

# --- Build stage: install deps into a venv ---
FROM python:3.13-slim AS build

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    VIRTUAL_ENV=/app/venv \
    PATH="/app/venv/bin:$PATH"

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .

RUN python -m venv "$VIRTUAL_ENV" \
    && pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# --- Runtime stage: slim image, non-root user ---
FROM python:3.13-slim

ARG UID=1001
ARG GID=1001
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    VIRTUAL_ENV=/app/venv \
    PATH="/app/venv/bin:$PATH" \
    PYTHONPATH="/app"

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && update-ca-certificates \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN groupadd -g "${GID}" appuser \
    && useradd --no-log-init -u "${UID}" -g "${GID}" --create-home appuser

COPY --from=build --chown=appuser:appuser /app/venv /app/venv
COPY --chown=appuser:appuser app/ /app/app/
COPY --chown=appuser:appuser data/ /app/data/
COPY --chown=appuser:appuser scripts/ /app/scripts/
COPY --chown=appuser:appuser app_car_rental.py /app/

RUN mkdir -p /app/.chroma /app/.checkpoints /app/logs \
    && chown -R appuser:appuser /app/.chroma /app/.checkpoints /app/logs

USER appuser

# Build the policy index at image build time so the container is ready to
# serve immediately — it only needs the local fastembed model, no API key.
RUN python scripts/build_index.py

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl --fail http://localhost:8081/health || exit 1

EXPOSE 8081

CMD ["uvicorn", "app_car_rental:app", "--host", "0.0.0.0", "--port", "8081"]
