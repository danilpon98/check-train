FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    DATA_DIR=/data WEB_HOST=0.0.0.0 WEB_PORT=8765 OPEN_BROWSER=0
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY trainwatch ./trainwatch
RUN mkdir -p /data
VOLUME ["/data"]
EXPOSE 8765
CMD ["python", "-m", "trainwatch", "run"]
