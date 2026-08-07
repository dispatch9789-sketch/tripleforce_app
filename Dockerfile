# Dockerfile for Triple Force Logistic LLC
# Production-ready container image

FROM python:3.10-slim

LABEL maintainer="Triple Force Logistic LLC"
LABEL description="Logistics Management Application"

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV FLASK_APP=run.py
ENV FLASK_ENV=production

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        gcc \
        libpq-dev \
        libc6 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

# Create uploads directory
RUN mkdir -p app/static/uploads

# Initialize database on first run
RUN python init_db.py || true

# Expose port
EXPOSE 5000

# Run with gunicorn
CMD ["gunicorn", "--config", "gunicorn.conf.py", "run:app"]
