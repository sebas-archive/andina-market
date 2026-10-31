# Propuestas fuera de alcance

Formato: propuesta · justificación (una línea). El equipo decide.

1. **Ajustar la carga máxima de la Tarea 4.8 a 300 req/s.** El escenario k6 llega a 200 req/s, pero RNF-03 y RNF-04 exigen 300 req/s; sin ese escalón la prueba no puede verificarlos.
2. **Puertos de host 8001–8004 vs. `--scale pedidos=3`.** Publicar un puerto fijo de host para `pedidos` impide escalarlo a 3 réplicas; propuesta: publicar solo el gateway y dejar los servicios en la red interna (puerto 8000).
3. **`*.pdf` en `.gitignore` vs. Tarea 8.3.** La Tarea 8.3 pide copia del informe en el repositorio, pero la Tarea 0.1 ignora todos los PDF; propuesta: excepción `!entrega/*.pdf`.
4. **Archivos no listados en la sección 2 del plan.** `db/seed.sql` (Tarea 4.1), `scripts/tls.sh` (Tarea 4.5) y `respaldos/` (Tarea 4.9) se crearán en sus tareas; propuesta: añadir `respaldos/` al `.gitignore`.
