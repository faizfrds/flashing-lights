# Production Dockerfile for Indonesia Flash Flood Early Warning System (FFEWS)
FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn uvicorn fastapi

# Copy application source code
COPY . .

# Expose HTTP port for Cloud Run / Container triggers
EXPOSE 8080

# Default entrypoint: Run the cloud HTTP service
CMD ["uvicorn", "cloud_app:app", "--host", "0.0.0.0", "--port", "8080"]

