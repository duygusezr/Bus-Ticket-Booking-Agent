# ============================================================
# Bus Ticket Booking Agent — Multi-stage Docker Build
# ============================================================
# Kullanım:
#   docker build -t ela-booking .
#   docker run -p 8001:8001 --env-file backend/.env ela-booking
#
# Docker Compose ile (önerilen):
#   docker compose up --build
# ============================================================

# ── Stage 1: Backend dependencies ────────────────────────────
FROM python:3.11-slim AS backend-deps

WORKDIR /app/backend

COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# ── Stage 2: Final image ─────────────────────────────────────
FROM python:3.11-slim

# Sistem bağımlılıkları (curl: healthcheck için)
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python paketlerini kopyala
COPY --from=backend-deps /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=backend-deps /usr/local/bin /usr/local/bin

# Backend kodu (database klasörü dahil)
COPY backend/ ./backend/

# Frontend static dosyaları
COPY frontend/ ./frontend/

# Çalışma dizini backend
WORKDIR /app/backend

# Ortam değişkenleri (varsayılanlar — docker-compose veya --env-file ile override edilir)
ENV PORT=8001
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:${PORT}/ || exit 1

EXPOSE ${PORT}

CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001", "--ws-ping-interval", "20", "--ws-ping-timeout", "20"]
