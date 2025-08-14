# Minimal production Dockerfile for a FastAPI app on a Docker-based PaaS (e.g., Render)
# - The platform typically injects $PORT; gunicorn is bound to 0.0.0.0:$PORT
# - ASGI app is exposed at main_fastapi:app
# - Dependencies installed from requirements.txt; no extra build tools added

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

WORKDIR /app

# Install dependencies first to leverage Docker layer caching
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir gunicorn

# Copy application code
COPY . .

# Start gunicorn with uvicorn worker, binding to the injected $PORT
CMD gunicorn main_fastapi:app -w 2 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT --timeout 600 --graceful-timeout 120 --keep-alive 120

