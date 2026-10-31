# Bloqueos

Formato: tarea · qué falló · salida del error · alternativa más barata.

## Tarea 3.1 · Render del diagrama Mermaid a PNG

- **Qué falló:** el agente no pudo ejecutar `npx @mermaid-js/mermaid-cli`; el entorno de ejecución bloqueó la descarga y ejecución de un paquete externo.
- **Salida:** `Permission for this action was denied ... Reason: [Code from External]`.
- **Alternativa más barata:** que un integrante ejecute el comando guardado en la cabecera de `docs/diagrama-arquitectura.mmd`, o pegue el archivo en https://mermaid.live y exporte PNG a 2000 px a `docs/evidencias/f3-01-arquitectura.png`. Otra opción es abrir `docs/diagrama-arquitectura.drawio` en draw.io y exportar PNG con el mismo nombre.
- **Resuelto (31/10/2026):** un integrante ejecutó el comando con `-p` apuntando a Chrome 131 instalado con `npx @puppeteer/browsers install chrome@131.0.6778.204`. El PNG quedó en 1984 × 1428 px y el texto se lee.

## Tarea 4.3 · Imagen de MinIO no disponible

- **Qué falló:** no se pudo descargar la imagen de MinIO ni de Docker Hub ni de quay.io.
- **Salida:** `pull access denied for minio/minio, repository does not exist or may require 'docker login'` y `quay.io/minio/minio:RELEASE.2024-12-18T13-15-44Z: 401 UNAUTHORIZED`.
- **Alternativa aplicada (recorte autorizado por la Tarea 4.3):** se conserva el endpoint de imágenes; los objetos se guardan en el volumen Docker `objetos` con la estructura `bucket/clave` y se sirven con URL firmadas por HMAC de 15 min (`GET /api/productos/imagenes/{clave}?exp=&firma=`), equivalentes a las URL prefirmadas de S3. Detalle en `docs/PROPUESTAS.md`.
