# syntax=docker/dockerfile:1.5

FROM python:3.11-slim AS runtime

ENV PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# System dependencies for building wheels
RUN apt-get update && \
    apt-get install --no-install-recommends -y build-essential curl && \
    rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md MANIFEST.in /app/
COPY src /app/src
COPY metadata /app/metadata
COPY docs /app/docs
COPY scripts /app/scripts

RUN python -m pip install --upgrade pip && \
    pip install gunicorn "uvicorn[standard]" && \
    pip install .

COPY deploy/gunicorn_conf.py /app/gunicorn_conf.py
COPY deploy/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Create non-root user to run the service
RUN adduser --disabled-password --gecos "" mcp && chown -R mcp /app
USER mcp

EXPOSE 8000
ENTRYPOINT ["/app/entrypoint.sh"]
