FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# tzdata makes TZ effective; ffmpeg extracts video posters (optional at runtime).
RUN apt-get update \
    && apt-get install -y --no-install-recommends tzdata ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /srv/backend

COPY pyproject.toml ./
COPY app ./app
RUN pip install .

COPY alembic.ini ./
COPY migrations ./migrations

RUN useradd --system --uid 10001 app \
    && mkdir -p /data/media \
    && chown app /data/media
USER app

EXPOSE 8000

# One worker: the login rate limiter keeps its state in process (DECISIONS.md D20).
# Proxy headers are trusted because only nginx can reach this port.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000 --workers 1 --proxy-headers --forwarded-allow-ips=* --log-config app/logging.json"]
