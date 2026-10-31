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

## Tarea 4.11 · Render de la Figura 2 (diagrama de la demo)

- **Qué falló:** el mismo bloqueo de la Tarea 3.1: el agente no puede ejecutar `npx @mermaid-js/mermaid-cli`.
- **Alternativa más barata:** ejecutar el comando de la cabecera de `docs/diagrama-demo.mmd` (con el mismo Chrome usado para la Figura 1) para generar `docs/evidencias/f4-01-demo.png`.
- **Resuelto (31/10/2026):** el equipo generó `docs/evidencias/f4-01-demo.png` (1584 × 557 px, commit `709afa0`); el agente verificó que se lee.

## Tarea 5.3 · Captura de la calculadora de AWS (`f5-01-calculadora.png`)

- **Qué falló:** la Calculadora de precios de AWS es una aplicación web interactiva; el agente no puede armar la estimación ni capturarla con fecha visible de forma confiable.
- **Alternativa aplicada:** los precios salen de la AWS Price List API oficial (URL y fecha de publicación de cada archivo en `docs/costos.md`, fuentes F1–F13), consultada el 31/10/2026.
- **Pendiente para el equipo:** cargar en https://calculator.aws los recursos de la Tabla C1 y guardar la captura con fecha en `docs/evidencias/f5-01-calculadora.png`; si el total difiere de 425,86 USD, avisar para revisar los supuestos.

## Tarea 5.3 · Costo actual de la infraestructura propia

- **Qué falló:** el caso de la guía y los datos canónicos del plan no declaran el costo actual de los servidores propios ni de su mantenimiento.
- **Salida:** `docs/costos.md` y §8 dejan la comparación marcada con `[verificar]`.
- **Pendiente para el equipo:** aportar la cifra (o un supuesto aprobado y documentado) para completar la línea de comparación.
