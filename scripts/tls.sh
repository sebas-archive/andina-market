#!/bin/sh
# Genera un certificado autofirmado para localhost si no existe (Tarea 4.5).
# Se ejecuta automáticamente al arrancar el contenedor nginx (/docker-entrypoint.d/).
# Uso manual: DIR=./certs sh scripts/tls.sh
set -eu
DIR="${DIR:-/etc/nginx/certs}"
mkdir -p "$DIR"
if [ ! -s "$DIR/localhost.crt" ]; then
  openssl req -x509 -newkey rsa:2048 -nodes -days 365 \
    -keyout "$DIR/localhost.key" -out "$DIR/localhost.crt" \
    -subj "/CN=localhost/O=AndinaMarket demo" \
    -addext "subjectAltName=DNS:localhost,IP:127.0.0.1"
  echo "tls.sh: certificado autofirmado creado en $DIR"
fi
