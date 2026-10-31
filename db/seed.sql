-- Datos iniciales: 20 productos en 4 categorías, 3 usuarios (1 admin) y stock (Tarea 4.1).
-- El hash bcrypt se calcula aquí, en el arranque; la contraseña viene de SEED_USUARIOS_PASSWORD.
\getenv seed_password SEED_USUARIOS_PASSWORD

INSERT INTO usuarios.usuario (email, nombre, password_hash, rol, email_verificado) VALUES
    ('admin@example.com',    'Administración', crypt(:'seed_password', gen_salt('bf', 12)), 'admin',   true),
    ('cliente1@example.com', 'Cliente Uno',    crypt(:'seed_password', gen_salt('bf', 12)), 'cliente', true),
    ('cliente2@example.com', 'Cliente Dos',    crypt(:'seed_password', gen_salt('bf', 12)), 'cliente', true);

INSERT INTO catalogo.producto (sku, nombre, categoria, precio) VALUES
    ('TEC-001', 'Audífonos inalámbricos',      'tecnologia', 189900),
    ('TEC-002', 'Teclado mecánico',             'tecnologia', 249900),
    ('TEC-003', 'Mouse ergonómico',             'tecnologia',  89900),
    ('TEC-004', 'Cargador USB-C 65 W',          'tecnologia', 119900),
    ('TEC-005', 'Memoria USB 128 GB',           'tecnologia',  59900),
    ('HOG-001', 'Cafetera de goteo',            'hogar',      159900),
    ('HOG-002', 'Juego de sartenes',            'hogar',      219900),
    ('HOG-003', 'Lámpara de escritorio',        'hogar',       79900),
    ('HOG-004', 'Cobija de algodón',            'hogar',       99900),
    ('HOG-005', 'Organizador de cocina',        'hogar',       49900),
    ('MOD-001', 'Chaqueta impermeable',         'moda',       279900),
    ('MOD-002', 'Tenis para correr',            'moda',       329900),
    ('MOD-003', 'Morral urbano',                'moda',       149900),
    ('MOD-004', 'Gorra deportiva',              'moda',        45900),
    ('MOD-005', 'Reloj análogo',                'moda',       199900),
    ('DEP-001', 'Balón de fútbol',              'deportes',    89900),
    ('DEP-002', 'Mancuernas 5 kg (par)',        'deportes',   129900),
    ('DEP-003', 'Esterilla de yoga',            'deportes',    69900),
    ('DEP-004', 'Botella térmica',              'deportes',    54900),
    ('DEP-005', 'Lazo de saltar',               'deportes',    29900);

-- Stock inicial: 100 unidades por producto, salvo uno cercano al umbral para probar la alerta.
INSERT INTO inventario.stock (producto_id, disponible)
SELECT id, CASE WHEN sku = 'DEP-005' THEN 12 ELSE 100 END FROM catalogo.producto;

-- Imagen de muestra para un producto por categoría; Productos sube el archivo a MinIO al arrancar.
UPDATE catalogo.producto SET imagen_key = 'seed/' || sku || '.png'
WHERE sku IN ('TEC-001', 'HOG-001', 'MOD-001', 'DEP-001');
