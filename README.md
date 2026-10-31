# AndinaMarket — Guía 7: Computación en la Nube

Demostración contenerizada y documentación de una arquitectura en la nube para el e-commerce ficticio AndinaMarket S.A.S.

## Requisitos

- Docker 24+ con Docker Compose.
- 4 GB de RAM libres.

## Arranque

```bash
cp .env.example .env
docker compose up -d --wait
```

## Entregables

| Entregable | Ubicación | Estado |
|---|---|---|
| Documento técnico | `docs/informe.md` → `entrega/Informe_Guia7_AndinaMarket.pdf` | pendiente |
| Diagrama de arquitectura | `docs/diagrama-arquitectura.mmd`, `docs/diagrama-arquitectura.drawio` | pendiente |
| Evidencias de implementación | `docs/evidencias/` → `entrega/Evidencias_Guia7.zip` | pendiente |
| Análisis de costos | `docs/costos.md` | pendiente |
| Referencias bibliográficas (APA 7) | `docs/referencias.md` | pendiente |

## Puertos

| Componente | Puerto |
|---|---|
| Gateway Nginx (HTTP) | 8080 |
| Gateway Nginx (HTTPS) | 8443 |
| Servicio usuarios | 8001 |
| Servicio productos | 8002 |
| Servicio pedidos | 8003 |
| Servicio inventario | 8004 |
| Prometheus | 9090 |
| PostgreSQL, MinIO, Grafana | pendiente (Fase 4) |
