# Multi-stage build for Flask app with Node.js frontend assets
FROM node:18-alpine AS frontend-builder

# Set working directory for frontend build
WORKDIR /app

# Copy package files
COPY package*.json ./

# Install Node.js dependencies
RUN npm ci --only=production

# Copy source files needed for build
COPY gulpfile.js ./
COPY app/static ./app/static

# Build frontend assets
RUN npm run build || echo "No build script found, skipping..."

# Python stage
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FLASK_APP=app \
    FLASK_ENV=production

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create app user
RUN useradd --create-home --shell /bin/bash app

# Set work directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY --chown=app:app . .

# Copy built frontend assets from frontend-builder stage
COPY --from=frontend-builder --chown=app:app /app/app/static ./app/static

# Create necessary directories
RUN mkdir -p logs instance recordings && \
    chown -R app:app logs instance recordings

# Switch to app user
USER app

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run gunicorn
CMD ["gunicorn", "--config", "gunicorn.conf.py", "app:create_app()"] 