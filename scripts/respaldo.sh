#!/usr/bin/env bash
# Respaldo y restauración verificada de PostgreSQL (Tarea 4.9).
# Uso:
#   bash scripts/respaldo.sh            -> pg_dump comprimido en respaldos/ y copia al almacén de objetos
#   bash scripts/respaldo.sh --probar   -> crea pedido, respalda, borra el pedido, restaura en una base
#                                          temporal y verifica que el pedido reaparece con el mismo ID
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; . ./.env; set +a

BASE="${BASE:-https://localhost:8443}"
CURL=(curl -sk --max-time 10)
PSQL=(docker compose exec -T db psql -U "$POSTGRES_USER" -v ON_ERROR_STOP=1 -tA)

respaldar() {
  # Deja la ruta del archivo en la variable global RESPALDO.
  mkdir -p respaldos
  RESPALDO="respaldos/andina-$(date -u +%Y%m%dT%H%M%SZ).dump"
  docker compose exec -T db pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc -Z 6 >"$RESPALDO"
  echo "respaldo: $RESPALDO ($(du -h "$RESPALDO" | cut -f1))"
  # Copia fuera del servidor de base de datos: bucket "respaldos" del almacén de objetos (volumen `objetos`,
  # recorte de MinIO documentado en docs/BLOQUEOS.md; en producción, bucket S3).
  docker compose exec -T -u 0 productos mkdir -p /data/objetos/respaldos
  docker compose cp "$RESPALDO" "productos:/data/objetos/respaldos/$(basename "$RESPALDO")" 2>/dev/null
  echo "copia en almacén de objetos: respaldos/$(basename "$RESPALDO")"
  docker compose exec -T productos ls -l /data/objetos/respaldos/ | tail -n +2 | tail -1
}

if [ "${1:-}" != "--probar" ]; then
  respaldar
  exit 0
fi

echo "== 1. Crear un pedido de prueba"
TOKEN=$("${CURL[@]}" -X POST "$BASE/api/usuarios/login" -H 'Content-Type: application/json' \
  -d "{\"email\":\"cliente2@example.com\",\"password\":\"$SEED_USUARIOS_PASSWORD\"}" | python3 -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')
PRODUCTO=$("${CURL[@]}" "$BASE/api/productos?pagina=1&tamano=1" | python3 -c 'import sys,json;print(json.load(sys.stdin)["items"][0]["id"])')
PEDIDO=$("${CURL[@]}" -X POST "$BASE/api/pedidos" -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d "{\"items\":[{\"producto_id\":\"$PRODUCTO\",\"cantidad\":1}]}" | python3 -c 'import sys,json;print(json.load(sys.stdin)["id"])')
echo "pedido creado: $PEDIDO"
"${PSQL[@]}" -d "$POSTGRES_DB" -c "SELECT id, estado, total FROM pedidos.pedido WHERE id = '$PEDIDO'"

echo "== 2. Respaldar"
respaldar

echo "== 3. Borrar el pedido (simula pérdida de datos)"
"${PSQL[@]}" -d "$POSTGRES_DB" -c "DELETE FROM pedidos.pedido WHERE id = '$PEDIDO'"
echo "filas con ese ID en $POSTGRES_DB: $("${PSQL[@]}" -d "$POSTGRES_DB" -c "SELECT count(*) FROM pedidos.pedido WHERE id = '$PEDIDO'")"

echo "== 4. Restaurar en la base temporal andina_restaurada"
inicio=$(date +%s%N)
"${PSQL[@]}" -d postgres -c "DROP DATABASE IF EXISTS andina_restaurada" -c "CREATE DATABASE andina_restaurada"
docker compose exec -T db pg_restore -U "$POSTGRES_USER" -d andina_restaurada --exit-on-error <"$RESPALDO"
fin=$(date +%s%N)
echo "tiempo de restauración: $(( (fin - inicio) / 1000000 )) ms"

echo "== 5. Verificar que el pedido reaparece con el mismo ID"
RESTAURADO=$("${PSQL[@]}" -d andina_restaurada -c "SELECT id || ' ' || estado || ' ' || total FROM pedidos.pedido WHERE id = '$PEDIDO'")
echo "en andina_restaurada: ${RESTAURADO:-<no encontrado>}"
"${PSQL[@]}" -d postgres -c "DROP DATABASE andina_restaurada" >/dev/null
[ "${RESTAURADO%% *}" = "$PEDIDO" ] || { echo "FALLA: el pedido no se recuperó" >&2; exit 1; }
echo "OK: pedido $PEDIDO recuperado desde $RESPALDO"
