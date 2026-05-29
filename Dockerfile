# A lightweight, secure Python base image
FROM python:3.11-slim

# Prevent Python from writing .pyc files and ensure immediate log output
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Run as non-root user instead of root, for better security
RUN useradd --create-home --shell /bin/bash appuser

# Copy requirements and set non-root ownership to avoid root layers
COPY --chown=appuser:appuser requirements.txt .

# Install dependencies without local cache to minimize final image size
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code with non-root permissions
COPY --chown=appuser:appuser app.py .

# Switch context to the secure non-root user
USER appuser

# Document that the application process listens on port 8080
EXPOSE 8080

# Run with Gunicorn production server limited to 1 worker due to in-memory store
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "app:app", "--workers", "1"]