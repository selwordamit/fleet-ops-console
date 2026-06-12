FROM python:3.12-slim

# Unbuffered stdout/stderr for readable container logs; no .pyc clutter.
ENV PYTHONUNBUFFERED=1 

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# alembic/env.py imports from app.core and app.models, so all three must be copied together.
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./alembic.ini

EXPOSE 8000

# Tables must exist before serving, so run migrations first, then Uvicorn.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
