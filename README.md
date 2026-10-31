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
| Gateway Nginx (HTTP, redirige a HTTPS) | 8080 |
| Gateway Nginx (HTTPS) | 8443 |
| Servicio usuarios | 8001 |
| Servicio productos | 8002 |
| Servicio pedidos | sin puerto publicado (se escala con `--scale`; acceso por el gateway) |
| Servicio inventario | 8004 |
| Prometheus | 9090 (configurable con `PROMETHEUS_PORT` en `.env`) |
| PostgreSQL | sin puerto publicado |
| Grafana (dashboard aprovisionado, acceso anónimo de lectura) | 3000 |

## Guion de demo

Flujo completo a través del gateway (`https://localhost:8443`, certificado autofirmado: por eso `-k`): registro → login → catálogo → pedido → pago → consulta. Requiere `python3` para leer el JSON.

```bash
curl -sk -X POST https://localhost:8443/api/usuarios/registro -H 'Content-Type: application/json' -d '{"email":"demo@example.com","password":"ClaveDemo123","nombre":"Demo"}'
TOKEN=$(curl -sk -X POST https://localhost:8443/api/usuarios/login -H 'Content-Type: application/json' -d '{"email":"demo@example.com","password":"ClaveDemo123"}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')
PRODUCTO=$(curl -sk 'https://localhost:8443/api/productos?pagina=1&tamano=5' | python3 -c 'import sys,json;print(json.load(sys.stdin)["items"][0]["id"])')
PEDIDO=$(curl -sk -X POST https://localhost:8443/api/pedidos -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d "{\"items\":[{\"producto_id\":\"$PRODUCTO\",\"cantidad\":2}]}" | python3 -c 'import sys,json;print(json.load(sys.stdin)["id"])')
curl -sk -X POST https://localhost:8443/api/pedidos/$PEDIDO/pago -H "Authorization: Bearer $TOKEN"
curl -sk https://localhost:8443/api/pedidos/$PEDIDO -H "Authorization: Bearer $TOKEN"
```

El pago es simulado y falla en el 10 % de los intentos (`PAGO_FALLA_PCT`); si devuelve 402, el stock reservado se libera. Usuarios de prueba creados por `db/seed.sql`: `admin@example.com` (admin), `cliente1@example.com` y `cliente2@example.com`, con la contraseña de `SEED_USUARIOS_PASSWORD`.
