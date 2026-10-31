#!/usr/bin/env bash
# Medición A (pedidos=1) y B (pedidos=3) con la misma prueba k6 (Tarea 4.8).
# Uso: bash scripts/escalar.sh   (requiere el sistema arriba; dura unos 8 minutos)
# Salidas: docs/evidencias/f4-07-carga-1-replica.txt, f4-08-carga-3-replicas.txt y f4-10-escalado-distribucion.txt
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; . ./.env; set +a

EVIDENCIAS=docs/evidencias

restablecer_stock() {
  # La prueba crea ~1.900 pedidos; sin esto el seed (100 unidades por producto) se agota y k6 mide 409.
  docker compose exec -T db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -q \
    -c "UPDATE inventario.stock SET disponible = 100000, reservado = 0"
}

esperar_salud() {
  # Tras una prueba, los servicios saturados pueden tardar en volver a healthy.
  local pendientes
  for _ in $(seq 1 60); do
    pendientes=$(docker compose ps --format '{{.Service}} {{.Health}}' | awk '$2 != "" && $2 != "healthy"' || true)
    [ -z "$pendientes" ] && return 0
    sleep 3
  done
  echo "servicios sin healthy: $pendientes" >&2; return 1
}

restaurar_stock_seed() {
  # Deja el inventario como lo crea db/seed.sql para no alterar la prueba de humo ni las pruebas unitarias.
  docker compose exec -T db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -q -c "
    UPDATE inventario.stock s SET disponible = CASE WHEN p.sku = 'DEP-005' THEN 12 ELSE 100 END, reservado = 0
    FROM catalogo.producto p WHERE p.id = s.producto_id"
}

muestrear_cpu() {
  # Una muestra de docker stats cada vez que termina la anterior (~2 s), hasta que se cree el archivo de parada.
  local salida="$1" parada="$2"
  while [ ! -f "$parada" ]; do
    docker stats --no-stream --format '{{.Name}} {{.CPUPerc}} {{.MemUsage}}' | grep -E 'pedidos|productos|inventario' >>"$salida" || true
  done
}

medir() {
  local replicas="$1" archivo="$2"
  local muestras parada
  muestras=$(mktemp); parada=$(mktemp -u)

  docker compose up -d --no-recreate --no-deps --scale pedidos="$replicas" pedidos >/dev/null 2>&1
  esperar_salud
  restablecer_stock
  {
    echo "# Medición con pedidos=$replicas — $(date --iso-8601=seconds)"
    echo "# Host: $(nproc) CPU, $(free -g | awk '/Mem:/ {print $2}') GB RAM"
    echo '$ docker compose --profile carga run --rm k6 run /pruebas/pedidos.js'
  } >"$archivo"

  muestrear_cpu "$muestras" "$parada" &
  local muestreador=$!
  set +e
  local crudo; crudo=$(mktemp)
  docker compose --profile carga run --rm k6 run --quiet /pruebas/pedidos.js >"$crudo" 2>&1
  echo "# código de salida de k6: $?" >>"$crudo"
  set -e
  # Las advertencias por solicitud fallida se resumen en un conteo para que la evidencia sea legible.
  echo "# advertencias 'Request Failed' de k6: $(grep -c 'msg="Request Failed"' "$crudo" || true)" >>"$archivo"
  grep -v 'msg="Request Failed"' "$crudo" | grep -v -E 'Container .* (Creating|Created)' >>"$archivo"
  rm -f "$crudo"
  touch "$parada"; wait "$muestreador"

  {
    echo
    echo "# CPU media por contenedor durante la prueba (docker stats, 100 % = 1 núcleo)"
    awk '{gsub("%", "", $2); suma[$1] += $2; n[$1]++} END {for (c in suma) printf "%-32s %6.1f %% (%d muestras)\n", c, suma[c] / n[c], n[c]}' "$muestras" | sort
  } >>"$archivo"
  rm -f "$muestras" "$parada"
}

echo "Medición A: pedidos=1"
medir 1 "$EVIDENCIAS/f4-07-carga-1-replica.txt"

nginx_inicio=$(docker inspect -f '{{.State.StartedAt}}' "$(docker compose ps -q nginx)")
desde=$(date --iso-8601=seconds)
echo "Medición B: pedidos=3"
medir 3 "$EVIDENCIAS/f4-08-carga-3-replicas.txt"

{
  echo '$ docker compose ps pedidos nginx'
  docker compose ps pedidos nginx --format 'table {{.Name}}\t{{.Status}}'
  echo
  echo "# Nginx no se reinició al escalar: StartedAt antes=$nginx_inicio después=$(docker inspect -f '{{.State.StartedAt}}' "$(docker compose ps -q nginx)")"
  echo
  echo "# POST /api/pedidos atendidos por cada réplica durante la medición B (logs de uvicorn)"
  docker compose logs --since "$desde" pedidos 2>/dev/null | grep '"POST /api/pedidos HTTP' | awk '{print $1}' | sort | uniq -c
  echo
  echo "# Upstreams usados por Nginx para /api/pedidos durante la medición B (access log del gateway)"
  docker compose logs --since "$desde" nginx 2>/dev/null | grep '"POST /api/pedidos ' | grep -o 'upstream=[0-9.:]*' | sort | uniq -c
} >"$EVIDENCIAS/f4-10-escalado-distribucion.txt"

restaurar_stock_seed
docker compose up -d --no-recreate --no-deps --scale pedidos=1 pedidos >/dev/null 2>&1
echo "Listo: $EVIDENCIAS/f4-07-carga-1-replica.txt, f4-08-carga-3-replicas.txt, f4-10-escalado-distribucion.txt"
