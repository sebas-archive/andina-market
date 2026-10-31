# Análisis de costos — AndinaMarket en AWS

Estimación mensual en USD para la arquitectura de §5 (Figura 1), región `us-east-1`. Todos los precios se consultaron el **31 de octubre de 2026** en la AWS Price List API, el catálogo oficial y legible por máquina de los precios bajo demanda de AWS. La columna «fuente» remite a la tabla de fuentes del final.

## Supuestos

| Supuesto | Valor | Origen |
|---|---|---|
| Horas por mes | 730 | Plan, Tarea 5.3 |
| Región | `us-east-1` | Datos canónicos (§1 del plan) |
| Tráfico de API | 10 req/s de media → 26,28 M solicitudes/mes | Datos canónicos: 900.000 visitas × ~30 solicitudes |
| Solicitudes a CloudFront | 5 por visita → 4,5 M/mes (el resto queda en caché del navegador) | Decisión de diseño |
| Datos | 20 GB en RDS, 4 GB de imágenes y 1 GB de interfaz web en S3 | Plan, Tarea 5.3 |
| Transferencia saliente | 150 GB/mes: 120 GB por CloudFront (borde de Sudamérica, usuarios en Colombia) y 30 GB de API por el ALB | Plan (150 GB); reparto: decisión de diseño |
| Cómputo base | 4 servicios × 2 tareas (mínimo de RNF-01), 0,5 vCPU y 1 GB por tarea | §6.3 |
| Pico de temporada | 300 req/s durante 2 h/día × 30 días; productos e inventario suben de 2 a 10 tareas (máximo de §6.3) | Datos canónicos y §6.3; duración: supuesto |
| ALB | 1 LCU de media; +3 LCU en horas pico | Supuesto, se ajusta con la métrica `ConsumedLCUs` |
| Logs | 1 KB por solicitud de API, retención de 30 días | Supuesto |
| Respaldos lógicos | 30 copias diarias de 1 GB en S3; los respaldos automáticos de RDS caben en la asignación gratuita (el precio F3 cobra solo el exceso) | Supuesto |
| Red privada | 5 VPC endpoints de interfaz (ECR API, ECR Docker, CloudWatch Logs, Secrets Manager, SQS) en 2 zonas; sin NAT Gateway | Decisión de diseño (§5) |
| WAF | 2 Web ACL (CloudFront y ALB) con 3 reglas cada una: límite por IP, reglas administradas comunes e inyección SQL | Decisión de diseño (§7.1) |
| Alarmas | 6 operativas (§7.5) + 16 creadas por las políticas de seguimiento de objetivo | §6.3 y §7.5 |
| No incluido | Capa gratuita, impuestos, soporte de AWS, dominio y certificado (ACM público), pasarela de pago | — |

## Escenario base (~40 req/s en hora pico)

**Tabla C1.** Costo mensual del escenario base.

| Recurso | Cantidad mensual | Precio unitario (fuente) | Subtotal USD |
|---|---|---|---|
| Fargate vCPU (8 tareas × 0,5 vCPU) | 2.920 vCPU-h | 0,04048 /vCPU-h (F1) | 118,20 |
| Fargate memoria (8 tareas × 1 GB) | 5.840 GB-h | 0,004445 /GB-h (F1) | 25,96 |
| RDS PostgreSQL db.t4g.medium Multi-AZ | 730 h | 0,129 /h (F3) | 94,17 |
| RDS almacenamiento gp3 Multi-AZ | 20 GB-mes | 0,23 /GB-mes (F3) | 4,60 |
| ALB (hora) | 730 h | 0,0225 /h (F4) | 16,43 |
| ALB LCU (1 LCU media) | 730 LCU-h | 0,008 /LCU-h (F4) | 5,84 |
| IPv4 públicas del ALB (2 zonas) | 1.460 h | 0,005 /h (F5) | 7,30 |
| VPC endpoints de interfaz (5 × 2 zonas) | 7.300 h | 0,01 /h (F5) | 73,00 |
| VPC endpoints, datos procesados | 10 GB | 0,01 /GB (F5) | 0,10 |
| S3 Standard (imágenes, SPA, respaldos) | 35 GB-mes | 0,023 /GB-mes (F6) | 0,81 |
| S3 solicitudes GET | 1.000.000 | 0,0000004 /solicitud (F6) | 0,40 |
| S3 solicitudes PUT | 1.000 | 0,000005 /solicitud (F6) | 0,01 |
| Transferencia a Internet desde el ALB | 30 GB | 0,09 /GB (F7) | 2,70 |
| CloudFront, transferencia en Sudamérica | 120 GB | 0,110 /GB (F8) | 13,20 |
| CloudFront, solicitudes HTTPS en Sudamérica | 4,5 M | 0,0000022 /solicitud (F8) | 9,90 |
| WAF: 2 Web ACL (CloudFront y ALB) | 2 | 5 /mes (F9) | 10,00 |
| WAF: 6 reglas (3 por Web ACL) | 6 | 1 /mes (F9) | 6,00 |
| WAF: solicitudes inspeccionadas | 30,78 M | 0,0000006 /solicitud (F9) | 18,47 |
| CloudWatch Logs, ingesta | 26,28 GB | 0,50 /GB (F10) | 13,14 |
| CloudWatch Logs, almacenamiento (30 días) | 26,28 GB-mes | 0,03 /GB-mes (F10) | 0,79 |
| CloudWatch alarmas | 22 | 0,10 /alarma-mes (F10) | 2,20 |
| Secrets Manager (6 secretos) | 6 | 0,40 /secreto-mes (F11) | 2,40 |
| Secrets Manager, llamadas a la API | 20.000 | 0,000005 /llamada (F11) | 0,10 |
| SQS, solicitudes de la cola de pagos | 90.000 | 0,0000004 /solicitud (F12) | 0,04 |
| ECR, almacenamiento de imágenes | 1 GB-mes | 0,10 /GB-mes (F13) | 0,10 |
| **Total** | | | **425,86** |

## Escenario pico de temporada (300 req/s con autoescalado)

La Tabla C2 muestra solo el **incremento** sobre el escenario base durante un mes de temporada.

**Tabla C2.** Incremento mensual en temporada.

| Recurso | Cantidad mensual | Precio unitario (fuente) | Subtotal USD |
|---|---|---|---|
| Fargate vCPU (+16 tareas × 0,5 vCPU × 60 h) | 480 vCPU-h | 0,04048 /vCPU-h (F1) | 19,43 |
| Fargate memoria (+16 tareas × 1 GB × 60 h) | 960 GB-h | 0,004445 /GB-h (F1) | 4,27 |
| ALB LCU adicionales (+3 LCU × 60 h) | 180 LCU-h | 0,008 /LCU-h (F4) | 1,44 |
| Transferencia a Internet desde el ALB | 64,1 GB | 0,09 /GB (F7) | 5,77 |
| CloudFront, transferencia en Sudamérica | 256,4 GB | 0,110 /GB (F8) | 28,21 |
| CloudFront, solicitudes HTTPS | 9,62 M | 0,0000022 /solicitud (F8) | 21,16 |
| WAF: solicitudes inspeccionadas | 65,78 M | 0,0000006 /solicitud (F9) | 39,47 |
| CloudWatch Logs, ingesta y almacenamiento | 56,16 GB | 0,50 + 0,03 /GB (F10) | 29,76 |
| **Total** | | | **149,51** |

El mes de temporada costaría **575,37 USD** (425,86 + 149,51). El tráfico del mes se multiplica por 3,14: a las 26,28 M solicitudes base se suman 56,16 M en horas pico. CloudFront, WAF y logs suman 118,60 USD (79 %) del incremento; Fargate, solo 23,70 USD (16 %). En temporada pesa más el costo por solicitud que el cómputo.

## Optimización

**Tabla C3.** Ahorro mensual estimado sobre el escenario base.

| Medida | Ahorro mensual USD |
|---|---|
| Derecho de dimensionamiento: usuarios y pedidos a 0,25 vCPU / 0,5 GB | 36,04 |
| Compute Savings Plan 1 año sin pago inicial sobre Fargate ya redimensionado | 21,62 |
| Instancia reservada RDS 1 año sin pago inicial (0,093 /h, F3) | 26,28 |
| Ciclo de vida S3: respaldos de más de 7 días a Glacier Instant Retrieval (0,004 /GB-mes, F6) | 0,44 |
| **Total** | **84,38** |

- El redimensionamiento se basa en la medición propia: pedidos usó como máximo un 6 % de un núcleo bajo carga (`f4-07`, `f4-08`). Usuarios no se midió bajo carga y se le aplica el mismo tamaño mínimo.
- El Savings Plan de cómputo baja Fargate de 0,04048 a 0,032384 USD/vCPU-h y de 0,004445 a 0,003556 USD/GB-h (F2), es decir un 20 %.
- Con las cuatro medidas, el escenario base queda en **341,48 USD/mes**.
- Este diseño no tiene NAT Gateway, así que la medida de «reducción de NAT» del plan no aplica. Su equivalente son los VPC endpoints, que cuestan 73,00 USD/mes. Reducirlos a una sola zona los dejaría en 36,50 USD/mes, pero crearía una dependencia de esa zona. La decisión queda para el equipo (`docs/PROPUESTAS.md`).

## Comparación con el presupuesto y con el costo actual

- **Presupuesto canónico:** el base supera el límite de 250 USD/mes en 175,86 USD (70 %); el optimizado lo supera en 91,48 USD (37 %).
- **Costo actual:** [verificar] el caso no declara el costo de los servidores propios ni del mantenimiento actual, así que no se puede comparar sin inventar una cifra. Se necesita el dato del equipo.

## Fuentes de precios (consultadas el 31/10/2026)

| ID | Servicio y tarifa | URL (AWS Price List API) | Publicación del archivo |
|---|---|---|---|
| F1 | AWS Fargate (ECS), vCPU-hora y GB-hora | https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonECS/current/us-east-1/index.json | 19/10/2026 |
| F2 | Compute Savings Plan, 1 año sin pago inicial | https://pricing.us-east-1.amazonaws.com/savingsPlan/v1.0/aws/AWSComputeSavingsPlan/20261029175641/us-east-1/index.json | 29/10/2026 |
| F3 | Amazon RDS for PostgreSQL (instancia Multi-AZ, gp3, reserva) | https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonRDS/current/us-east-1/index.json | 29/10/2026 |
| F4 | Elastic Load Balancing (ALB, LCU) | https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AWSELB/current/us-east-1/index.json | 11/09/2026 |
| F5 | Amazon VPC (endpoints, IPv4 pública) | https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonVPC/current/us-east-1/index.json | 16/10/2026 |
| F6 | Amazon S3 (Standard, Glacier Instant Retrieval, solicitudes) | https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonS3/current/us-east-1/index.json | 15/10/2026 |
| F7 | Transferencia de datos a Internet | https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AWSDataTransfer/current/us-east-1/index.json | 16/09/2026 |
| F8 | Amazon CloudFront (Sudamérica) | https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonCloudFront/current/index.json | 19/10/2026 |
| F9 | AWS WAF | https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/awswaf/current/us-east-1/index.json | 14/09/2026 |
| F10 | Amazon CloudWatch (logs, alarmas) | https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonCloudWatch/current/us-east-1/index.json | 07/10/2026 |
| F11 | AWS Secrets Manager | https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AWSSecretsManager/current/us-east-1/index.json | 11/09/2026 |
| F12 | Amazon SQS | https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AWSQueueService/current/us-east-1/index.json | 11/09/2026 |
| F13 | Amazon ECR | https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonECR/current/us-east-1/index.json | 11/09/2026 |
