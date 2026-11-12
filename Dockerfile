FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Asia/Tashkent

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
# Windows'dan kelgan CRLF qator oxirlarini tozalaymiz (aks holda skript ishlamaydi)
RUN sed -i 's/\r$//' docker-entrypoint.sh && chmod +x docker-entrypoint.sh && mkdir -p uploads staticfiles

EXPOSE 8000
ENTRYPOINT ["./docker-entrypoint.sh"]
CMD ["waitress-serve", "--listen=0.0.0.0:8000", "--threads=8", "--channel-timeout=300", "config.wsgi:application"]
