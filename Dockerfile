FROM python:3.11-slim

# Çalışma dizini
WORKDIR /app

# Sistem bağımlılıkları (ses işleme için gerekli olabilecekler)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Önce requirements kopyala (Docker cache optimizasyonu)
COPY backend/requirements.txt ./requirements.txt

# CPU-only PyTorch + diğer bağımlılıklar
RUN pip install --no-cache-dir -r requirements.txt

# Backend kodunu kopyala
COPY backend/ ./

# Veritabanı ve veri dosyalarını kopyala
COPY database/ ./database/

# PORT ortam değişkeni Railway tarafından otomatik atanır
ENV PORT=8001

# Uvicorn ile başlat
CMD python -m uvicorn main:app --host 0.0.0.0 --port ${PORT}
