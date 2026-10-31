#!/usr/bin/env bash
# Prueba de humo de punta a punta a través del gateway (Tarea 4.7).
# Uso: bash scripts/humo.sh   (requiere el sistema arriba: docker compose up -d --wait)
# Sale con código distinto de 0 si cualquier paso falla. Es idempotente: crea un usuario nuevo en cada ejecución.
set -euo pipefail

BASE="${BASE:-https://localhost:8443}"
CURL=(curl -sk --max-time 10)

paso() { printf '\n[%s] %s\n' "$(date +%T)" "$*"; }
falla() { printf 'FALLA: %s\n' "$*" >&2; exit 1; }
json() { python3 -c "import sys,json; print(json.load(sys.stdin)$1)"; }

# Llama a la API, imprime el cuerpo y verifica el código HTTP esperado.
api() {
  local esperado="$1"; shift
  local salida codigo cuerpo
  salida=$("${CURL[@]}" -w '\n%{http_code}' "$@") || falla "sin respuesta de $*"
  codigo="${salida##*$'\n'}"; cuerpo="${salida%$'\n'*}"
  printf '  HTTP %s %s\n' "$codigo" "$cuerpo" | cut -c1-220 >&2
  [ "$codigo" = "$esperado" ] || falla "se esperaba HTTP $esperado y llegó $codigo"
  printf '%s' "$cuerpo"
}

inicio=$SECONDS

paso "1. Esperando healthchecks de los contenedores"
for intento in $(seq 1 60); do
  pendientes=$(docker compose ps --format '{{.Service}} {{.Health}}' | awk '$2 != "" && $2 != "healthy"' || true)
  [ -z "$pendientes" ] && "${CURL[@]}" -o /dev/null "$BASE/health" && break
  [ "$intento" = 60 ] && falla "servicios sin healthy: $pendientes"
  sleep 2
done
docker compose ps --format '  {{.Service}}: {{.Health}}' | sort

EMAIL="humo-$(date +%s)-$RANDOM@example.com"
PASSWORD="ClaveHumo123"

paso "2. Registro de $EMAIL"
api 201 -X POST "$BASE/api/usuarios/registro" -H 'Content-Type: application/json' \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\",\"nombre\":\"Humo\"}" >/dev/null

paso "3. Login"
TOKEN=$(api 200 -X POST "$BASE/api/usuarios/login" -H 'Content-Type: application/json' \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}" | json '["access_token"]')
AUTH=(-H "Authorization: Bearer $TOKEN")

paso "4. Listado de productos"
PRODUCTOS=$(api 200 "$BASE/api/productos?pagina=1&tamano=5")
PRODUCTO=$(printf '%s' "$PRODUCTOS" | json '["items"][1]["id"]')
[ -n "$PRODUCTO" ] || falla "el catálogo no devolvió productos"

paso "5. Stock antes del pedido"
ANTES=$(api 200 "$BASE/api/inventario/$PRODUCTO" | json '["disponible"]')
CANTIDAD=2
[ "$ANTES" -ge "$CANTIDAD" ] || falla "stock insuficiente para la prueba ($ANTES)"

paso "6. Creación de pedido ($CANTIDAD unidades)"
PEDIDO=$(api 201 -X POST "$BASE/api/pedidos" "${AUTH[@]}" -H 'Content-Type: application/json' \
  -d "{\"items\":[{\"producto_id\":\"$PRODUCTO\",\"cantidad\":$CANTIDAD}]}" | json '["id"]')

paso "7. Consulta del pedido"
ESTADO=$(api 200 "$BASE/api/pedidos/$PEDIDO" "${AUTH[@]}" | json '["estado"]')
[ "$ESTADO" = "creado" ] || falla "estado inesperado: $ESTADO"

paso "8. Verificación de inventario"
DESPUES=$(api 200 "$BASE/api/inventario/$PRODUCTO" | json '["disponible"]')
echo "  disponible antes=$ANTES después=$DESPUES diferencia=$((ANTES - DESPUES)) esperado=$CANTIDAD"
[ $((ANTES - DESPUES)) -eq "$CANTIDAD" ] || falla "el stock no bajó exactamente $CANTIDAD unidades"

printf '\nOK: prueba de humo superada en %s s\n' "$((SECONDS - inicio))"
