FROM nginx:1.27.3-alpine
RUN apk add --no-cache openssl
COPY scripts/tls.sh /docker-entrypoint.d/40-tls.sh
