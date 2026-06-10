# Backend image: FastAPI app served by Uvicorn.
# On startup it applies DB migrations (alembic upgrade head), then starts the API.
FROM python:3.12-slim

# Unbuffered stdout/stderr for readable container logs; no .pyc clutter.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Install dependencies first so this layer stays cached when only app code changes.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Application code and migration assets.
# alembic env.py imports app.core.config / app.models, so both must be present.
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./alembic.ini

EXPOSE 8000

# Tables must exist before serving, so run migrations first, then Uvicorn.
# DATABASE_URL / REDIS_URL are supplied by the environment (docker-compose).
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
