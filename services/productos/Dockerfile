FROM python:3.12.8-slim AS build
WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.12.8-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/srv
COPY --from=build /install /usr/local
RUN useradd --create-home --uid 10001 app && mkdir -p /data/objetos && chown app /data/objetos
WORKDIR /srv
COPY pytest.ini .
COPY app ./app
COPY imagenes_seed ./imagenes_seed
COPY tests ./tests
USER app
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --retries=5 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
