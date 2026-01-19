# ===========================================
# Book Translator - Docker Configuration
# ===========================================
# Multi-stage build for smaller image size
# Usage:
#   docker build -t book-translator .
#   docker run -p 5001:5001 -v ./translations:/app/translations book-translator

# Stage 1: Build stage
FROM python:3.12-slim as builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir \
    Flask==3.1.2 \
    Flask-CORS==6.0.2 \
    requests==2.32.3 \
    psutil==5.9.8 \
    Werkzeug==3.1.3 \
    gunicorn==23.0.0

# Stage 2: Production stage
FROM python:3.12-slim as production

# Create non-root user for security
RUN groupadd -r translator && useradd -r -g translator translator

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application code
COPY translator.py config.py ./
COPY static/ ./static/

# Create necessary directories with correct permissions
RUN mkdir -p uploads translations logs && \
    chown -R translator:translator /app

# Switch to non-root user
USER translator

# Environment variables
ENV FLASK_ENV=production \
    BOOK_TRANSLATOR_HOST=0.0.0.0 \
    BOOK_TRANSLATOR_PORT=5001 \
    VERBOSE_DEBUG=false \
    OLLAMA_API_URL=http://host.docker.internal:11434/api/generate

# Expose port
EXPOSE 5001

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:5001/health', timeout=5)" || exit 1

# Run with gunicorn for production
CMD ["gunicorn", "--bind", "0.0.0.0:5001", "--workers", "2", "--threads", "4", "--timeout", "300", "translator:app"]
