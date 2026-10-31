# Propuestas fuera de alcance

Formato: propuesta · justificación (una línea). El equipo decide.

1. **Ajustar la carga máxima de la Tarea 4.8 a 300 req/s.** El escenario k6 llega a 200 req/s, pero RNF-03 y RNF-04 exigen 300 req/s; sin ese escalón la prueba no puede verificarlos.
2. **Puertos de host 8001–8004 vs. `--scale pedidos=3`.** Publicar un puerto fijo de host para `pedidos` impide escalarlo a 3 réplicas; propuesta: publicar solo el gateway y dejar los servicios en la red interna (puerto 8000).
3. **`*.pdf` en `.gitignore` vs. Tarea 8.3.** La Tarea 8.3 pide copia del informe en el repositorio, pero la Tarea 0.1 ignora todos los PDF; propuesta: excepción `!entrega/*.pdf`.
4. **Archivos no listados en la sección 2 del plan.** `db/seed.sql` (Tarea 4.1), `scripts/tls.sh` (Tarea 4.5) y `respaldos/` (Tarea 4.9) se crearán en sus tareas; propuesta: añadir `respaldos/` al `.gitignore`.
5. **Verificación de email (RF-01) sin endpoint en el contrato de API.** El plan exige "registro con email verificado" pero el contrato no tiene ruta de verificación; propuesta: declararlo como límite de la demo en §6.5 o añadir `GET /api/usuarios/verificar?token=`.
6. **Alerta de stock bajo (RF-04) sin endpoint ni mecanismo en la Fase 4.** Ninguna tarea implementa el umbral de 10 unidades; propuesta: registrar un evento en log al cruzar el umbral y verificarlo en la prueba de inventario, o declararlo como límite en §6.5.
7. **Liberación de reserva sin ruta en el contrato.** La Tarea 4.3 pide liberación, pero el contrato solo tiene `POST /api/inventario/{id}/reservar`; propuesta: `POST /api/inventario/{id}/liberar` (interno, `X-Service-Token`).
8. **Pago síncrono en el contrato vs. cola SQS en la arquitectura.** El contrato de API devuelve el resultado del pago en la misma respuesta (200/402), mientras §5.2 procesa el pago por SQS de forma asíncrona; propuesta: declarar en §6.5 que la demo simplifica el pago a síncrono.
