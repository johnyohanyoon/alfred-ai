# Alfred AI
FROM python:3.11-slim

# Basic system packages
RUN apt-get update && apt-get install -y \
    curl \
    gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY --chown=99:100 . /app/

# Create necessary directories
RUN mkdir -p /app/{data,logs,exports} && \
    chown -R 99:100 /app && \
    chmod -R 755 /app

# Run as non-root user
USER 99:100

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Start with uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]