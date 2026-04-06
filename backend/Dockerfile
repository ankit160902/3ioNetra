FROM python:3.11-slim-bullseye

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip setuptools wheel

ENV PIP_USE_PEP517=0
ENV PIP_NO_BUILD_ISOLATION=1
ENV PIP_DEFAULT_TIMEOUT=300
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
ENV PIP_NO_CACHE_DIR=1

# Bake models into image
RUN mkdir -p /app/models/embeddings /app/models/reranker

COPY requirements.txt .
RUN pip install --use-deprecated=legacy-resolver -r requirements.txt

COPY . .

# Pre-download models during build phase
RUN python scripts/download_models.py

# Force offline mode for runtime
ENV TRANSFORMERS_OFFLINE=1
ENV HF_HUB_OFFLINE=1

EXPOSE 8080

# Use shell form for CMD to allow environment variable expansion ($PORT)
# This is critical for Google Cloud Run compatibility
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080} --workers 1 --timeout-keep-alive 65
