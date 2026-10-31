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

## 4. Selección del modelo de nube

### 4.1 Comparación de modelos de servicio

La Tabla 4 evalúa cada modelo con los cinco criterios de la guía, expresando la consecuencia para AndinaMarket y no la definición del modelo.

**Tabla 4.** Comparación de IaaS, PaaS y SaaS para AndinaMarket.

| Modelo | Costos de infraestructura y mantenimiento | Facilidad de desarrollo y despliegue | Capacidad de escalamiento | Seguridad y control | Administración técnica |
|---|---|---|---|---|---|
| IaaS (EC2 autoadministrado) | Elimina la compra de servidores, pero mantiene el costo de horas de operación para parches y monitoreo de cada instancia. | El equipo debe construir la cadena de despliegue sobre máquinas virtuales antes de entregar funcionalidad. | Escala con grupos de instancias, pero el equipo debe construir y probar las imágenes de máquina y las reglas de escalado para la ráfaga de 600 req/s. | Control máximo del sistema operativo; el cliente responde por sus parches y su firewall (AWS, s.f.-a). | Alta: sin equipo de operaciones, el mantenimiento recae en los desarrolladores. |
| PaaS / CaaS (ECS Fargate, RDS) | Pago por vCPU y memoria asignadas a cada tarea; sin servidores que mantener. | Se despliega la misma imagen Docker de la demo; CPU y memoria se declaran por tarea (AWS, s.f.-b). | Réplicas por servicio ajustables entre 2 y 10 según la carga, lo que cubre el pico de 300 req/s. | AWS gestiona servidores y parches del entorno; el cliente controla red, IAM, cifrado y código (AWS, s.f.-a). | Baja: no hay que aprovisionar ni escalar clústeres de máquinas virtuales (AWS, s.f.-b). |
| SaaS (plataforma de e-commerce cerrada) | Pago por suscripción o por transacción según el proveedor, que crece con los 30.000 pedidos/mes y el 35 % de crecimiento anual. | Inmediata para funciones estándar; limitada para la reserva de stock con compensación (RF-04). | La escala el proveedor, sin control de AndinaMarket sobre umbrales ni réplicas. | Los datos de clientes y pedidos quedan bajo políticas del proveedor, con poco control de cifrado y auditoría. | Mínima, a cambio de depender del proveedor para cambios y migración. |

PaaS/CaaS es el único modelo que combina baja carga de administración con control sobre la seguridad de los datos y la lógica propia de pedidos e inventario; IaaS exige operación que el equipo no tiene y SaaS cede el control de los datos de pago y de los flujos críticos.

### 4.2 Decisión tecnológica y justificación

Los pesos de la Tabla 5 priorizan escalamiento y administración técnica (25 % cada uno), porque las caídas en temporada son el primer problema del caso y la empresa no cuenta con equipo de operaciones. Los puntajes de 1 a 5 son una valoración del equipo a partir de la Tabla 4.

**Tabla 5.** Matriz de decisión ponderada.

| Criterio | Peso | IaaS | PaaS/CaaS | SaaS |
|---|---|---|---|---|
| Costos de infraestructura y mantenimiento | 20 % | 3 | 4 | 3 |
| Facilidad de desarrollo y despliegue | 15 % | 2 | 4 | 3 |
| Capacidad de escalamiento | 25 % | 3 | 5 | 4 |
| Seguridad y control | 15 % | 5 | 4 | 2 |
| Administración técnica | 25 % | 1 | 4 | 5 |
| **Resultado ponderado** | **100 %** | **2,65** | **4,25** | **3,60** |

Se elige PaaS/CaaS: contenedores administrados en AWS ECS Fargate, base de datos RDS PostgreSQL Multi-AZ, archivos estáticos e imágenes en S3 servidos por CloudFront, balanceador ALB, secretos en Secrets Manager y observabilidad en CloudWatch. Fargate ejecuta las mismas imágenes Docker de la demostración sin administrar servidores (AWS, s.f.-b), y RDS Multi-AZ mantiene una instancia en espera en otra zona de disponibilidad para la conmutación por error (AWS, s.f.-c), lo que atiende RNF-01 y RNF-04 sin personal de operaciones.

Se descarta IaaS puro porque su mayor control (5 en seguridad y control) no compensa el puntaje de 1 en administración técnica: el equipo tendría que parchar sistemas operativos y configurar el escalado de instancias, tareas que hoy causan los costos fijos y las interrupciones que el caso busca eliminar.

Se descarta SaaS cerrado porque la reserva de stock con compensación (RF-04), la degradación controlada del catálogo (RNF-01) y el control del cifrado y la auditoría (RNF-02) dependerían de las extensiones que ofrezca el proveedor, y sus comisiones crecerían con el volumen de pedidos.

**Modelo de despliegue.** Se usa nube pública en la región `us-east-1`, con los servicios de aplicación y datos en subredes privadas. La plataforma no almacena datos de tarjeta: el pago se delega a una pasarela externa, simulada en la demostración, y los datos personales se guardan cifrados en RDS y S3. Se descarta nube híbrida porque mantener servidores propios conservaría los costos fijos del caso y añadiría enlaces y operación en dos entornos sin un requisito regulatorio que lo exija.

**Responsabilidad compartida.** AWS protege la infraestructura que ejecuta sus servicios y el cliente responde por lo que configura dentro de ellos, según el servicio utilizado (AWS, s.f.-a; AWS, s.f.-d):

- Infraestructura física y red de AWS: responsabilidad de AWS.
- Cómputo (Fargate): AWS mantiene y parcha el entorno de ejecución; AndinaMarket define imágenes, CPU, memoria y políticas IAM de cada tarea (AWS, s.f.-b).
- Base de datos (RDS): AWS opera respaldos y replicación; AndinaMarket configura VPC, grupos de seguridad, TLS, cifrado en reposo y usuarios de la base (AWS, s.f.-d).
- Almacenamiento (S3): AWS opera la plataforma; AndinaMarket clasifica los datos, elige el cifrado y fija permisos con IAM (AWS, s.f.-a).
- Aplicación y datos: AndinaMarket responde por el código, la autenticación JWT, la autorización por rol y los datos de clientes.

La Tabla 6 resume los servicios seleccionados y su rol en la solución.

**Tabla 6.** Servicios de AWS seleccionados.

| Servicio | Rol en la solución |
|---|---|
| Amazon CloudFront + AWS WAF | Entrega de la interfaz web y filtrado de tráfico malicioso en el borde. |
| Amazon S3 | Interfaz web estática, imágenes de producto y copias de respaldo. |
| Application Load Balancer (ALB) | Punto de entrada HTTPS, enrutamiento por ruta y reparto entre réplicas. |
| Amazon ECS en AWS Fargate | Ejecución de los servicios de usuarios, productos, pedidos e inventario. |
| Amazon RDS PostgreSQL Multi-AZ | Base de datos con un esquema por dominio y conmutación por error entre zonas. |
| Amazon SQS | Cola para el procesamiento asíncrono de pagos. |
| AWS Secrets Manager | Custodia de credenciales de base de datos y del secreto JWT. |
| AWS IAM | Permisos mínimos para tareas, operadores y servicios. |
| Amazon CloudWatch | Métricas, registros y alarmas de los servicios. |
