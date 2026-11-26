# Development image for the Django API and the Celery worker (same image, different command).
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install dependencies first so Docker caches this layer until requirements change.
COPY requirements.txt requirements-dev.txt ./
RUN pip install -r requirements-dev.txt

# In dev, compose mounts ./backend over /app so code edits apply without rebuilding.
COPY . .

EXPOSE 8000
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
