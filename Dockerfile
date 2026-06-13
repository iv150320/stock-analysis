FROM python:3.10-slim

# System deps for matplotlib (used by the CLI plotting path only)
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first so Docker can cache the layer when only code changes
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application code
COPY app.py config.py project.py README.md ./
COPY templates/ ./templates/
COPY static/ ./static/

# NOTE: This container is intentionally run as root inside a private Docker
# network.  The bind-mounted /app/charts volume is managed by the host and
# works correctly only when the process matches the volume's owner (root).

EXPOSE 5000

# Use gunicorn for production. 2 workers, 120s timeout matches yfinance budget + headroom.
CMD ["gunicorn", "app:app", \
     "--bind", "0.0.0.0:5000", \
     "--workers", "2", \
     "--timeout", "120", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]

# Quick TCP-level probe; the /health endpoint gives the real answer
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request, sys; \
        sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:5000/health', timeout=3).status == 200 else 1)"
