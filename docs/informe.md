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

## 5. Arquitectura

La Figura 1 presenta la arquitectura propuesta. Los números de los nodos corresponden a los siete elementos mínimos de la guía: (1) usuarios, (2) interfaz web, (3) punto de entrada, (4) servicios de dominio, (5) base de datos y almacenamiento, (6) seguridad y control de acceso, y (7) monitoreo, registros y copias de seguridad. Las flechas indican protocolo y sentido; las líneas discontinuas son flujos de control, registro o respaldo.

![Figura 1. Arquitectura de AndinaMarket en AWS.](evidencias/f3-01-arquitectura.png)

**Figura 1.** Arquitectura de AndinaMarket en AWS. Fuente editable: `docs/diagrama-arquitectura.mmd` y `docs/diagrama-arquitectura.drawio`.

Solo el ALB está en subred pública. Los cuatro servicios y la base de datos están en subredes privadas, sin dirección IP pública, y alcanzan S3, SQS, Secrets Manager y CloudWatch mediante VPC endpoints.

### 5.1 Justificación por componente

La Tabla 7 justifica cada componente de la Figura 1 y registra la alternativa descartada.

**Tabla 7.** Justificación de componentes.

| Componente | Servicio concreto | Función en el sistema | Por qué | Alternativa descartada y motivo |
|---|---|---|---|---|
| CDN + WAF | Amazon CloudFront + AWS WAF | Entrega la interfaz y filtra tráfico malicioso antes de la VPC. | Descarga del ALB el contenido estático y bloquea ataques en el borde (RNF-02). | Servir la interfaz desde el ALB: consume capacidad de los servicios en temporada. |
| Interfaz web y app | SPA en S3 | Interfaz para navegadores y móviles; mantiene el carrito en el cliente. | Archivos estáticos sin servidores que operar. | Renderizado en servidor: añade un quinto servicio que escalar. |
| API Gateway / Balanceador | Application Load Balancer | Termina TLS, enruta por ruta (`/api/pedidos`…) y reparte entre réplicas. | Se integra con los servicios de ECS en Fargate (AWS, s.f.-b). | Amazon API Gateway: duplica el enrutamiento que ya hace el ALB. |
| Servicio Usuarios | ECS Fargate | Registro, login, emisión de JWT y roles (RF-01). | Escala aparte del catálogo; el login no depende de pedidos. | Autenticación dentro de cada servicio: duplica la lógica de credenciales. |
| Servicio Productos | ECS Fargate | Catálogo, búsqueda e imágenes (RF-02). | Recibe la mayor parte del tráfico de lectura y debe seguir activo si falla pedidos (RNF-01). | Unir catálogo y pedidos: una falla de pedidos tumbaría el catálogo. |
| Servicio Pedidos | ECS Fargate | Crea pedidos, calcula totales y orquesta la reserva y el pago (RF-03). | Concentra la carga de escritura del pico; escala de forma independiente (RNF-04). | Orquestación en la interfaz: el total quedaría en manos del cliente. |
| Servicio Inventario | ECS Fargate | Existencias, reserva y liberación por SKU (RF-04). | Una sola fuente de verdad del stock evita sobreventa con reserva transaccional. | Descontar stock desde pedidos: rompería el aislamiento por dominio. |
| Base de datos | RDS PostgreSQL Multi-AZ | Persistencia con un esquema por dominio (`usuarios`, `catalogo`, `pedidos`, `inventario`). | Réplica síncrona en otra zona con conmutación automática (AWS, s.f.-e); transacciones para la reserva. | DynamoDB: la reserva con `SELECT ... FOR UPDATE` y `CHECK` exige un modelo relacional. |
| Almacenamiento de archivos | Amazon S3 | Imágenes de producto, interfaz web y respaldos. | Servicio administrado; el cliente decide cifrado y permisos (AWS, s.f.-a). | Volumen de disco en los contenedores: se pierde al reemplazar una tarea. |
| Cola de pagos | Amazon SQS | Desacopla el pedido de la respuesta de la pasarela externa. | Si la pasarela tarda o falla, el pedido no se pierde y se reintenta. | Llamada síncrona: un pago lento bloquea la creación de pedidos en el pico. |
| Seguridad y control de acceso | AWS IAM + Secrets Manager + JWT | Permisos mínimos por tarea, custodia de secretos y autorización por rol. | El secreto JWT y las credenciales de RDS no viven en el código ni en la imagen. | Variables de entorno en la definición de tarea: el secreto queda visible en la configuración. |
| Monitoreo y registros | Amazon CloudWatch | Métricas, logs y alarmas de los cuatro servicios y de RDS. | Integrado con ECS y RDS, sin servidores de monitoreo propios. | Prometheus y Grafana autogestionados: se usan en la demo, pero en producción exigen operarlos. |
| Pasarela de pago externa | Proveedor de pagos (simulado en la demo) | Procesa el cobro; la plataforma no almacena datos de tarjeta. | Saca los datos de tarjeta del alcance de la plataforma (RNF-02). | Procesar tarjetas en un servicio propio: amplía la superficie de riesgo del caso. |

**Aislamiento de datos.** Cada servicio se conecta a RDS con un usuario propio que solo tiene permisos sobre su esquema. Ningún servicio lee tablas de otro dominio: Productos obtiene el stock de Inventario por HTTP, y Pedidos reserva unidades mediante el endpoint interno de Inventario protegido con `X-Service-Token`.

### 5.2 Flujos de comunicación

**Compra completa.** Los pasos usan los nombres de los componentes de la Figura 1.

1. Los Usuarios: web y móvil abren la Interfaz web y app (SPA en S3) a través de CDN + WAF (CloudFront) por HTTPS.
2. La interfaz envía `POST /api/usuarios/login` al API Gateway / Balanceador (ALB), que lo enruta al Servicio Usuarios; este verifica el hash en RDS y emite un JWT de 15 min firmado con el secreto de Secrets Manager.
3. La interfaz consulta `GET /api/productos`; el Servicio Productos lee el esquema `catalogo` en RDS, pide el stock al Servicio Inventario con un tiempo límite de 500 ms y devuelve URL firmadas de las imágenes guardadas en el nodo «S3: imágenes, respaldos».
4. El usuario arma el carrito en la interfaz, sin llamadas al servidor.
5. La interfaz envía `POST /api/pedidos` con el token Bearer y una cabecera `Idempotency-Key`; el Servicio Pedidos valida el token y calcula el total con los precios del catálogo.
6. El Servicio Pedidos llama a `POST /api/inventario/{id}/reservar` del Servicio Inventario, que bloquea la fila con `SELECT ... FOR UPDATE` y descuenta las unidades, o responde 409 `stock_insuficiente`.
7. El Servicio Pedidos guarda el pedido en estado `creado` en RDS; si la escritura falla, solicita a Inventario liberar la reserva (compensación).
8. La interfaz envía `POST /api/pedidos/{id}/pago`; el Servicio Pedidos publica la solicitud en la Cola SQS: pagos.
9. El consumidor de la cola, dentro del Servicio Pedidos, invoca la Pasarela de pago externa por HTTPS.
10. Si el pago se aprueba, el pedido pasa a `pagado`; si se rechaza, Pedidos solicita a Inventario liberar la reserva.
11. El Servicio Inventario registra el movimiento en `inventario.movimiento` y, si el disponible baja de 10 unidades, emite la alerta a CloudWatch: métricas, logs, alarmas, que la reenvía como Alertas al equipo.
12. La interfaz consulta `GET /api/pedidos/{id}` y muestra la confirmación; los cuatro servicios envían sus registros a CloudWatch.

**Flujo degradado.** La Tabla 8 describe el efecto de cada falla sobre el flujo anterior.

**Tabla 8.** Comportamiento ante fallas.

| Falla | Efecto visible | Mecanismo | Tiempo de recuperación |
|---|---|---|---|
| Cae una tarea del Servicio Pedidos | Ninguno si quedan otras réplicas; algunas solicitudes en curso pueden fallar. | El ALB deja de enviar tráfico a la tarea que no responde y ECS la reemplaza. | Se mide en la demo (§7.4). |
| Caen todas las tareas del Servicio Pedidos | No se pueden crear ni pagar pedidos; el catálogo y el login siguen disponibles. | Servicios independientes detrás del ALB (degradación controlada, RNF-01). | Hasta que ECS levanta nuevas tareas; se mide en la demo (§7.4). |
| Falla el Servicio Inventario | El catálogo responde con `stock: null`; no se pueden crear pedidos. | Tiempo límite de 500 ms en Productos y respuesta de respaldo. | Igual que la recuperación de una tarea de ECS. |
| La Cola SQS: pagos no está disponible | Los pedidos quedan en estado `creado` sin procesar el pago. | El pedido y la reserva ya están persistidos; la solicitud de pago se reintenta. | Depende de AWS; no lo controla AndinaMarket. |
| RDS pierde la zona primaria | Errores de conexión durante la conmutación; luego el servicio se reanuda. | Conmutación automática a la réplica en espera; los servicios deben reconectarse (AWS, s.f.-f). | Típicamente 60–120 s (AWS, s.f.-f). |

**Flujo de respaldo.** RDS sube los registros de transacciones a S3 cada cinco minutos y permite restaurar a cualquier instante dentro del periodo de retención (AWS, s.f.-g), lo que cumple el RPO de 15 min de RNF-01. Se respaldan:

- La base de datos completa, con respaldos automáticos diarios y registros de transacciones; retención de 30 días.
- Una copia lógica diaria (`pg_dump`) en el bucket S3 de respaldos, independiente del mecanismo de RDS.
- Las imágenes de producto en S3, con versionado de objetos.

La restauración crea una instancia nueva a partir del instante elegido, sin modificar la original (AWS, s.f.-g). Después se actualiza el endpoint de conexión en Secrets Manager y se reinician las tareas de ECS. Cada mes se ensaya la restauración midiendo su duración frente al RTO de 4 h; en la demo se ensaya con `scripts/respaldo.sh` (§7.3).
