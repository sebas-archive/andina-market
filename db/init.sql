-- Esquemas por dominio, roles por servicio y tablas mínimas (Tarea 4.1).
-- Cada servicio se conecta con su propio rol y solo tiene permisos sobre su esquema.
\getenv svc_password POSTGRES_PASSWORD

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE SCHEMA usuarios;
CREATE SCHEMA catalogo;
CREATE SCHEMA pedidos;
CREATE SCHEMA inventario;

CREATE ROLE svc_usuarios   LOGIN PASSWORD :'svc_password';
CREATE ROLE svc_catalogo   LOGIN PASSWORD :'svc_password';
CREATE ROLE svc_pedidos    LOGIN PASSWORD :'svc_password';
CREATE ROLE svc_inventario LOGIN PASSWORD :'svc_password';

-- usuarios ---------------------------------------------------------------
CREATE TABLE usuarios.usuario (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    email             text NOT NULL UNIQUE,
    nombre            text NOT NULL,
    password_hash     text NOT NULL,
    rol               text NOT NULL DEFAULT 'cliente' CHECK (rol IN ('cliente', 'admin')),
    email_verificado  boolean NOT NULL DEFAULT false,
    intentos_fallidos integer NOT NULL DEFAULT 0,
    primer_fallo      timestamptz,
    bloqueado_hasta   timestamptz,
    created_at        timestamptz NOT NULL DEFAULT now(),
    updated_at        timestamptz NOT NULL DEFAULT now()
);

-- catalogo ---------------------------------------------------------------
CREATE TABLE catalogo.producto (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    sku        text NOT NULL UNIQUE,
    nombre     text NOT NULL,
    categoria  text NOT NULL,
    precio     numeric(12, 2) NOT NULL CHECK (precio > 0),
    imagen_key text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

-- inventario -------------------------------------------------------------
-- Sin llave foránea hacia catalogo: los dominios no se referencian entre sí.
CREATE TABLE inventario.stock (
    producto_id uuid PRIMARY KEY,
    disponible  integer NOT NULL CHECK (disponible >= 0),
    reservado   integer NOT NULL DEFAULT 0 CHECK (reservado >= 0),
    umbral      integer NOT NULL DEFAULT 10,
    updated_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE inventario.movimiento (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    producto_id uuid NOT NULL REFERENCES inventario.stock (producto_id),
    tipo        text NOT NULL CHECK (tipo IN ('reserva', 'liberacion', 'ajuste')),
    cantidad    integer NOT NULL CHECK (cantidad > 0),
    referencia  text,
    created_at  timestamptz NOT NULL DEFAULT now()
);

-- pedidos ----------------------------------------------------------------
CREATE TABLE pedidos.pedido (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    usuario_id uuid NOT NULL,
    estado     text NOT NULL DEFAULT 'creado'
               CHECK (estado IN ('creado', 'pagado', 'enviado', 'entregado', 'cancelado')),
    total      numeric(12, 2) NOT NULL CHECK (total >= 0),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE pedidos.pedido_item (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    pedido_id       uuid NOT NULL REFERENCES pedidos.pedido (id) ON DELETE CASCADE,
    producto_id     uuid NOT NULL,
    cantidad        integer NOT NULL CHECK (cantidad > 0),
    precio_unitario numeric(12, 2) NOT NULL
);

CREATE TABLE pedidos.idempotencia (
    clave      text NOT NULL,
    usuario_id uuid NOT NULL,
    pedido_id  uuid NOT NULL REFERENCES pedidos.pedido (id) ON DELETE CASCADE,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (clave, usuario_id)
);

-- Permisos explícitos: cada rol solo ve su esquema -----------------------
REVOKE ALL ON SCHEMA public FROM PUBLIC;

GRANT USAGE ON SCHEMA usuarios   TO svc_usuarios;
GRANT USAGE ON SCHEMA catalogo   TO svc_catalogo;
GRANT USAGE ON SCHEMA pedidos    TO svc_pedidos;
GRANT USAGE ON SCHEMA inventario TO svc_inventario;

GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA usuarios   TO svc_usuarios;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA catalogo   TO svc_catalogo;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA pedidos    TO svc_pedidos;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA inventario TO svc_inventario;
