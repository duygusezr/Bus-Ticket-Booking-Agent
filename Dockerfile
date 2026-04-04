FROM python:3.11-slim

WORKDIR /app/backend

# Gereksinimler önce kopyalanır (Docker katman önbellekleme optimizasyonu)
COPY backend/requirements.txt ./requirements.txt

RUN pip install --no-cache-dir -r requirements.txt

# Backend kodu kopyalanır (database klasörü dahil)
COPY backend/ ./

# PORT Railway tarafından otomatik atanır
ENV PORT=8001

CMD python -m uvicorn main:app --host 0.0.0.0 --port ${PORT}
