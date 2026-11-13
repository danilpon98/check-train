# --- 1. сборка фронтенда (Vue 3 + Vite) ---
FROM node:22-alpine AS frontend
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
# vite кладёт сборку в ../trainwatch/static
RUN npm run build

# --- 2. сервис (Python) ---
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    DATA_DIR=/data WEB_HOST=0.0.0.0 WEB_PORT=8765 OPEN_BROWSER=0
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY trainwatch ./trainwatch
COPY --from=frontend /build/trainwatch/static ./trainwatch/static
# Постоянные данные (база, ключи push) — в /data. docker compose монтирует туда ./data,
# на Railway подключите Volume с путём /data. Инструкцию VOLUME Railway не поддерживает.
RUN mkdir -p /data
# порт: 8765 по умолчанию; хостинг (Railway) задаёт свой через PORT — он важнее
EXPOSE 8765
CMD ["python", "-m", "trainwatch", "run"]
