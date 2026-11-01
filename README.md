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
|------------|-----------|--------|
| Documento técnico | [`docs/informe.md`](docs/informe.md) → `entrega/Informe_Guia7_AndinaMarket.pdf` (se genera con `scripts/exportar.sh`) | Completo; faltan los datos de portada marcados `[verificar]` |
| Diagrama de arquitectura | [`docs/diagrama-arquitectura.mmd`](docs/diagrama-arquitectura.mmd), [`.drawio`](docs/diagrama-arquitectura.drawio), PNG en [`docs/evidencias/f3-01-arquitectura.png`](docs/evidencias/f3-01-arquitectura.png) | Completo |
| Evidencias de implementación | [`docs/evidencias/`](docs/evidencias/) → [`entrega/Evidencias_Guia7.zip`](entrega/Evidencias_Guia7.zip) (índice: Anexo A del informe) | Completo; falta `f5-01-calculadora.png` (ver `docs/BLOQUEOS.md`) |
| Análisis de costos | [`docs/costos.md`](docs/costos.md) e informe §8 | Completo; falta el costo actual del caso (`[verificar]`) |
| Referencias bibliográficas (APA 7) | [`docs/referencias.md`](docs/referencias.md) e informe §10 | Completo (15 fuentes) |

Exportar el informe a PDF (requiere Docker y Chrome o Chromium):

```bash
CHROME=/ruta/a/chrome bash scripts/exportar.sh
```

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

## Interfaz web

Con el sistema arriba, abrir `https://localhost:8443/` (certificado autofirmado: aceptar la advertencia del navegador). Permite navegar el catálogo, iniciar sesión con un usuario de prueba, armar el carrito, crear y pagar pedidos y ver «Mis pedidos». Fuente: `web/`. Está fuera del alcance del plan (`docs/PROPUESTAS.md`, punto 21).

## Guion de demo

Flujo completo a través del gateway (`https://localhost:8443`, certificado autofirmado: por eso `-k`): registro, login, catálogo, pedido , pago , consulta. Requiere `python3` para leer el JSON.

```bash
curl -sk -X POST https://localhost:8443/api/usuarios/registro -H 'Content-Type: application/json' -d '{"email":"demo@example.com","password":"ClaveDemo123","nombre":"Demo"}'
TOKEN=$(curl -sk -X POST https://localhost:8443/api/usuarios/login -H 'Content-Type: application/json' -d '{"email":"demo@example.com","password":"ClaveDemo123"}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')
PRODUCTO=$(curl -sk 'https://localhost:8443/api/productos?pagina=1&tamano=5' | python3 -c 'import sys,json;print(json.load(sys.stdin)["items"][0]["id"])')
PEDIDO=$(curl -sk -X POST https://localhost:8443/api/pedidos -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d "{\"items\":[{\"producto_id\":\"$PRODUCTO\",\"cantidad\":2}]}" | python3 -c 'import sys,json;print(json.load(sys.stdin)["id"])')
curl -sk -X POST https://localhost:8443/api/pedidos/$PEDIDO/pago -H "Authorization: Bearer $TOKEN"
curl -sk https://localhost:8443/api/pedidos/$PEDIDO -H "Authorization: Bearer $TOKEN"
```

El pago es simulado y falla en el 10 % de los intentos (`PAGO_FALLA_PCT`); si devuelve 402, el stock reservado se libera. Usuarios de prueba creados por `db/seed.sql`: `admin@example.com` (admin), `cliente1@example.com` y `cliente2@example.com`, con la contraseña de `SEED_USUARIOS_PASSWORD`.

Las fotos del catálogo de muestra son de Wikimedia Commons con licencias libres; autor, licencia y enlace de cada una están en [`services/productos/imagenes_seed/CREDITOS.md`](services/productos/imagenes_seed/CREDITOS.md).
