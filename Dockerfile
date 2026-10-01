# Imagen de producción (Railway): backend + front en un solo servicio.
# Para desarrollo local usar docker compose.
FROM python:3.13-slim
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/app ./app
COPY frontend/public ./public
RUN mkdir -p /data
# en Railway montar un volumen en /data y definir SUPER_PASSWORD
ENV STATIC_DIR=/app/public DATA_DIR=/data
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips="*"
