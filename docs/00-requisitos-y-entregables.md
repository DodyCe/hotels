# 0. Requisitos y entregables

Relación entre lo que pide la guía del proyecto final y dónde se cumple en este repositorio.

**Proyecto:** 6. Sistema de Reservas Hoteleras.

**Integrantes:** (completar con nombres y rol de cada uno).

## 0.1 Requisitos técnicos mínimos (sección 3 de la guía)

| Requisito | Cómo se cumple | Dónde |
|---|---|---|
| Mínimo 5 microservicios funcionales | 6 microservicios y un Gateway | `services/`, [02-microservicios.md](02-microservicios.md) |
| Responsabilidad clara de cada servicio | Responsabilidad y límite descritos por servicio | [02-microservicios.md](02-microservicios.md) |
| APIs REST documentadas | GET, POST, PATCH, PUT y DELETE con códigos HTTP por caso | [openapi.yaml](openapi.yaml), `/docs.html` |
| Base de datos por servicio, sin compartir tablas | 6 proyectos PostgreSQL separados en Supabase | [03-modelo-de-datos.md](03-modelo-de-datos.md) |
| API Gateway como punto de entrada | `gateway.py` en el puerto 8080 | [02-microservicios.md](02-microservicios.md) |
| Autenticación y autorización justificada | Sesión opaca en cookie `HttpOnly`, roles guest y admin, bloqueo por intentos | [05-seguridad.md](05-seguridad.md), decisión D5 |
| Comunicación por API y asíncrona | HTTP con JSON y patrón outbox con reintentos | [01-arquitectura.md](01-arquitectura.md), decisión D6 |
| Manejo de errores y respuestas HTTP | Errores JSON con 400, 401, 403, 404, 405, 409, 413, 415, 429, 500 y 503 | [02-microservicios.md](02-microservicios.md) |
| Docker y docker-compose | `Dockerfile` y `compose.yaml` con 7 contenedores y healthchecks, probado en CI | [08-manual-instalacion-y-usuario.md](08-manual-instalacion-y-usuario.md) |
| Swagger/OpenAPI | OpenAPI 3.1 público e interno, Swagger UI en el Gateway | `/docs.html`, [openapi.yaml](openapi.yaml), [internal-openapi.yaml](internal-openapi.yaml) |
| Logs y monitoreo básico | Logs por servicio, `/health`, `/api/readiness` y `/status.html` | [06-logs-y-monitoreo.md](06-logs-y-monitoreo.md) |
| Pruebas documentadas | Siete suites automáticas, flujo de demostración y CI | [07-plan-de-pruebas.md](07-plan-de-pruebas.md) |
| Git/GitHub | Ramas por tema, pull requests y GitHub Actions | Historial del repositorio |
| Diagramas de arquitectura y comunicación | Mermaid en Markdown | [01-arquitectura.md](01-arquitectura.md) |
| Demostración de flujo completo | Guion paso a paso y script de respaldo | [09-guion-sustentacion.md](09-guion-sustentacion.md), `tools/demo_flujo.py` |

## 0.2 Funcionalidades del caso (sección 4 de la guía)

| Pide la guía | Implementado |
|---|---|
| Consultar disponibilidad | `GET /api/availability` por rango de fechas |
| Registrar una reserva | `POST /api/reservations` con precio calculado en el servidor |
| Actualizar el inventario | Asignación y liberación en Inventario; ajuste manual desde el panel admin |
| Generar la confirmación | Evento `reservation.confirmed` y correo desde Notificaciones |
| Huéspedes | Cuentas en Autenticación y perfiles gestionados por el administrador |
| Hoteles y habitaciones | Catálogo y Habitaciones con administración completa |
| Pagos (posible) | No incluido. El total se calcula y se muestra, pero no se cobra |

## 0.3 Entregables (sección 5 de la guía)

| Entregable | Archivo | Estado |
|---|---|---|
| Código fuente de todos los microservicios | `gateway.py`, `services/`, `web/` | Listo |
| Repositorio Git con historial de commits | Este repositorio | Listo |
| README con instalación y ejecución | [README.md](../README.md) | Listo |
| docker-compose | [compose.yaml](../compose.yaml) | Listo, verificado en CI |
| Documentación Swagger/OpenAPI | [openapi.yaml](openapi.yaml), [internal-openapi.yaml](internal-openapi.yaml), `/docs.html` | Listo |
| Diagrama general de arquitectura | [01-arquitectura.md](01-arquitectura.md) | Listo |
| Diagrama de comunicación entre microservicios | [01-arquitectura.md](01-arquitectura.md) | Listo |
| Modelo de datos de cada servicio | [03-modelo-de-datos.md](03-modelo-de-datos.md) | Listo |
| Decisiones técnicas y tecnologías | [04-decisiones-tecnicas.md](04-decisiones-tecnicas.md) | Listo |
| Plan y evidencias de pruebas | [07-plan-de-pruebas.md](07-plan-de-pruebas.md), [evidencias/](evidencias/) | Listo. Faltan capturas con Supabase y del correo recibido |
| Manual breve de instalación y usuario | [08-manual-instalacion-y-usuario.md](08-manual-instalacion-y-usuario.md) | Listo |
| Presentación de sustentación | [09-guion-sustentacion.md](09-guion-sustentacion.md) es la base | Faltan las diapositivas |
| Demostración funcional | [09-guion-sustentacion.md](09-guion-sustentacion.md) | Falta ensayarla |

## 0.4 Criterios de evaluación (sección 7 de la guía)

| Criterio | Peso | Material de apoyo |
|---|---|---|
| Arquitectura de microservicios | 20 % | 01, 02, 03 |
| Funcionalidad | 20 % | Demostración, `tools/demo_flujo.py` |
| Tecnología e implementación | 20 % | 04, 05, `compose.yaml` |
| Calidad y pruebas | 15 % | 06, 07, GitHub Actions |
| Documentación | 10 % | Carpeta `docs/` y README |
| Sustentación | 15 % | 09 |

## 0.5 Pendiente del equipo

Lo que no se puede resolver desde el código:

1. Completar los integrantes y el rol de cada uno en este documento.
2. Hacer las diapositivas a partir de [09-guion-sustentacion.md](09-guion-sustentacion.md), con los diagramas de 01.
3. Ensayar la demostración con las bases Supabase y el correo configurado.
4. Añadir a `evidencias/` una captura del correo recibido en Gmail y capturas con las bases reales (`/status.html` y el panel de Supabase).
5. Correr `tests/integration.py --six-postgres` antes de la entrega y guardar la salida en `evidencias/`.
6. Si hay Docker en algún equipo, correr `docker compose up --build` y guardar una captura de `docker compose ps`.
7. Decidir si se publica en Vercel y Render (ver la parte E del manual).
8. Repartir las diez etapas del guion entre los integrantes.
