## 3. Requerimientos

Los requerimientos responden a los cuatro problemas del caso: caídas en temporadas de alta demanda, interrupciones del servicio, costos fijos altos de servidores propios y riesgo de seguridad de los datos de pago. Las métricas usan los datos canónicos de AndinaMarket: 180.000 usuarios registrados, 12.000 SKU, carga nominal de 40 req/s y pico de temporada de 300 req/s.

### 3.1 Requerimientos funcionales

La Tabla 1 presenta un requerimiento funcional por dominio; cada criterio de verificación corresponde a un endpoint del contrato de API de la demostración (§6).

**Tabla 1.** Requerimientos funcionales.

| ID | Requerimiento | Importancia | Criterio de verificación |
|---|---|---|---|
| RF-01 | El sistema registra usuarios con email verificado, autentica con credenciales, emite un token de sesión con rol `cliente` o `admin` y bloquea la cuenta tras 5 intentos fallidos en 15 min. | La identidad es la base de la autorización de pedidos y de la administración del catálogo. El bloqueo limita la fuerza bruta sobre 180.000 cuentas. Sin roles, cualquier cliente podría modificar precios. | `POST /api/usuarios/registro` devuelve 201 y 409 si el email existe; `POST /api/usuarios/login` devuelve 200 con token, 401 inválido y 423 al sexto intento; `GET /api/usuarios/me` devuelve 401 sin token. |
| RF-02 | El sistema ofrece el catálogo con búsqueda y paginación, muestra en el detalle la disponibilidad actual leída del inventario, restringe alta y edición al rol `admin` y asocia una imagen a cada producto. | El catálogo concentra la mayor parte del tráfico de lectura. Mostrar stock actual evita vender lo que no hay. Restringir la escritura protege precios y descripciones de 12.000 SKU. | `GET /api/productos?pagina=1&tamano=5` devuelve 5 ítems con `stock`; `GET /api/productos/{id}` devuelve 404 si no existe; `POST /api/productos` devuelve 403 con rol `cliente` y 201 con `admin`. |
| RF-03 | El sistema crea pedidos con varios ítems, calcula el total con los precios del catálogo, valida el stock contra inventario, gestiona los estados `creado → pagado → enviado → entregado` y permite consultar el historial del usuario. | El pedido es la transacción que genera ingresos (30.000 al mes). Calcular el total en el servidor impide manipular precios desde el cliente. Validar stock antes de confirmar evita sobreventa. | `POST /api/pedidos` devuelve 201 con total correcto para 2 ítems y 409 `stock_insuficiente` sin stock; `POST /api/pedidos/{id}/pago` cambia el estado a `pagado`; `GET /api/pedidos` lista solo los pedidos del usuario. |
| RF-04 | El sistema controla las existencias por SKU, reserva unidades al crear un pedido, las libera si el pago falla y genera una alerta cuando el stock disponible baja de 10 unidades. | La reserva evita que dos pedidos simultáneos tomen la misma unidad. La liberación devuelve al catálogo las unidades de pagos rechazados. La alerta permite reabastecer antes del agotamiento. | `POST /api/inventario/{id}/reservar` descuenta `disponible` y devuelve 409 sin stock; tras `POST /api/pedidos/{id}/pago` con 402, `GET /api/inventario/{producto_id}` muestra las unidades repuestas. |

### 3.2 Requerimientos no funcionales

La Tabla 2 fija una métrica, una unidad y una condición de medición para cada atributo de calidad exigido por la guía.

**Tabla 2.** Requerimientos no funcionales.

| ID | Requerimiento | Importancia | Criterio de verificación |
|---|---|---|---|
| RNF-01 Disponibilidad | Disponibilidad mensual ≥ 99,9 % (≤ 43 min de indisponibilidad), RTO de 4 h y RPO de 15 min; si falla el servicio de pedidos, el catálogo sigue respondiendo en modo lectura. | Las interrupciones del servicio son uno de los problemas actuales del caso. La degradación controlada conserva la navegación del catálogo, que es la mayor parte del tráfico, aunque no se puedan crear pedidos. | Prueba de restauración del respaldo con medición de tiempo y parada del contenedor `pedidos` comprobando que `GET /api/productos` sigue devolviendo 200. |
| RNF-02 Seguridad | Tráfico externo solo por TLS 1.2 o superior; contraseñas con hash bcrypt o Argon2; tokens JWT con expiración de 15 min; permisos mínimos por rol; cifrado en reposo de base de datos y almacenamiento; registro de auditoría de cada acceso. | La plataforma maneja datos personales y de pago, cuyo riesgo de exposición es uno de los problemas del caso. Un token de vida corta limita el uso de credenciales robadas. | Inspección de `curl -v` u `openssl s_client` contra el gateway; consulta de la columna de hash en `usuarios.usuario`; prueba de que un token vencido devuelve 401; matriz de autorización (§7.1). |
| RNF-03 Rendimiento | Latencia p95 ≤ 500 ms en endpoints de consulta y ≤ 800 ms en `POST /api/pedidos`, con tasa de error < 1 % bajo un pico de 300 req/s. | La latencia en el catálogo y en el pago incide directamente en el abandono de la compra. El umbral de errores acota los pedidos perdidos en temporada alta. | Prueba de carga k6 con umbrales `http_req_duration{p(95)}` y `http_req_failed`, con la salida guardada en `docs/evidencias/`. |
| RNF-04 Escalabilidad | Sostener 300 req/s (7,5× la carga nominal de 40 req/s) con p95 ≤ 1 s (2× la latencia base) mediante escalado horizontal automático de 2 a 10 réplicas por servicio. | Las caídas en temporada de alta demanda son el primer problema del caso. El crecimiento anual de 35 % en pedidos exige que la capacidad crezca sin rediseñar la plataforma. | Comparación de la prueba k6 con 1 y 3 réplicas de `pedidos`; inspección de la política de autoescalado propuesta (mínimo 2, máximo 10 tareas). |

### 3.3 Trazabilidad

La Tabla 3 relaciona cada requerimiento con el componente que lo satisface y con la evidencia que lo comprueba; se reutiliza en §5 y §6.

**Tabla 3.** Trazabilidad de requerimientos.

| Requerimiento | Componente de arquitectura | Evidencia |
|---|---|---|
| RF-01 | Servicio Usuarios + IAM/Secrets Manager/JWT | Pruebas pytest de `usuarios`; `docs/evidencias/f4-06-humo.txt` |
| RF-02 | Servicio Productos + S3 (imágenes) | Pruebas pytest de `productos`; respuesta de `GET /api/productos` |
| RF-03 | Servicio Pedidos + Cola SQS (pagos) | Pruebas pytest de `pedidos`; guion de demo del README |
| RF-04 | Servicio Inventario + RDS PostgreSQL | Pruebas pytest de `inventario`; verificación de stock en `f4-06-humo.txt` |
| RNF-01 | RDS PostgreSQL Multi-AZ + S3 (respaldos) + ALB | `docs/evidencias/f4-09-restauracion.txt`; escenarios de falla (§7.4) |
| RNF-02 | CDN + WAF, ALB, IAM + Secrets Manager + JWT | Salida TLS y cabeceras del gateway; matriz de autorización (§7.1) |
| RNF-03 | ALB + servicios + CloudWatch | `docs/evidencias/f4-07-carga-1-replica.txt` |
| RNF-04 | ALB + ECS Service Auto Scaling | `docs/evidencias/f4-07-carga-1-replica.txt` y `f4-08-carga-3-replicas.txt` |
