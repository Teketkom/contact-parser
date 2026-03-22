# ── Stage 1: Builder ──────────────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Stage 2: Runtime ───────────────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

WORKDIR /app

# Install runtime system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl wget ca-certificates \
    libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 \
    libdrm2 libxkbcommon0 libgbm1 libgtk-3-0 \
    libxrandr2 libxfixes3 libxcomposite1 libxdamage1 \
    libcups2 libpango-1.0-0 libcairo2 libdbus-1-3 libatspi2.0-0 \
    fonts-liberation fonts-noto-color-emoji fonts-unifont \
    && rm -rf /var/lib/apt/lists/*

# Check if libasound2 or libasound2t64 is available
RUN apt-get update && (apt-get install -y --no-install-recommends libasound2t64 || apt-get install -y --no-install-recommends libasound2 || true) && rm -rf /var/lib/apt/lists/*

# Copy installed Python packages
COPY --from=builder /install /usr/local

# Create appuser FIRST so Playwright installs to correct home
RUN useradd --create-home --shell /bin/bash appuser && \
    mkdir -p /app/results /app/logs /app/data

# Install Playwright browsers as appuser (so they go to /home/appuser/.cache)
USER appuser
ENV PLAYWRIGHT_BROWSERS_PATH=/home/appuser/.cache/ms-playwright
RUN pip install --no-cache-dir --user playwright && \
    python -m playwright install chromium

USER root
# Copy application code
COPY --chown=appuser:appuser . .
RUN chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=5 \
    CMD curl -f http://localhost:8000/health || exit 1

ENV PLAYWRIGHT_BROWSERS_PATH=/home/appuser/.cache/ms-playwright
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--loop", "asyncio"]
