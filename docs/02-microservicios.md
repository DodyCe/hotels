# 2. Microservicios y APIs

Hotels tiene **seis microservicios** y un **API Gateway**. Cada servicio es un proceso Python independiente, con su propio puerto, su propia base PostgreSQL y su propio contrato en Swagger.

| Servicio | Puerto | Archivo | Base de datos |
|---|---|---|---|
| API Gateway | 8080 | `gateway.py` | No tiene |
| Autenticación | 8101 | `services/auth.py` | `hotels_auth` |
| Notificaciones | 8102 | `services/notifications.py` | `hotels_notifications` |
| Reservas | 8103 | `services/reservations.py` | `hotels_reservations` |
| Catálogo de hoteles | 8104 | `services/catalog.py` | `hotels_catalog` |
| Habitaciones | 8105 | `services/rooms.py` | `hotels_rooms` |
| Disponibilidad e inventario | 8106 | `services/availability.py` | `hotels_availability` |

Todos los servicios responden `GET /health`. El código compartido (servidor HTTP, conexión a la base, errores y llamadas internas) está en `services/common.py`, `services/postgres.py` y `services/validation.py`.

**Contratos:**

- Público: [`docs/openapi.yaml`](openapi.yaml), OpenAPI 3.1.
- Interno: [`docs/internal-openapi.yaml`](internal-openapi.yaml).
- Visor Swagger UI: `http://127.0.0.1:8080/docs.html`. Permite probar la API pública con la sesión abierta y muestra el contrato interno sin ejecutarlo.

Las rutas de esta página se escriben como las ve el navegador, con el prefijo `/api`. El Gateway quita ese prefijo antes de reenviar.

## 2.1 API Gateway

**Responsabilidad:** único punto de entrada. Recibe `/api/*`, decide el servicio por el primer segmento de la ruta y reenvía la petición con la clave interna. Sirve además el frontend, los contratos OpenAPI y Swagger UI.

**Qué no hace:** no guarda datos ni decide permisos de negocio. Cada servicio comprueba sus propias reglas.

| Prefijo | Servicio destino |
|---|---|
| `/api/auth/*`, `/api/guests*` | Autenticación |
| `/api/notifications` | Notificaciones |
| `/api/reservations*` | Reservas |
| `/api/hotels*` | Catálogo |
| `/api/rooms*` | Habitaciones |
| `/api/inventory*`, `/api/availability` | Disponibilidad e inventario |

**Rutas propias:**

- `GET /api/readiness`: consulta el `/health` de los seis servicios y devuelve `ready` y el estado de cada uno.
- `GET /openapi.json` y `GET /openapi-internal.json`: contratos convertidos de YAML a JSON.
- `/docs.html`, `/admin.html`, `/status.html`, `/reset-password.html`: páginas del frontend.

**Controles:** acepta solo los métodos GET, POST, PATCH, PUT y DELETE; limita el cuerpo a 16 KB; valida `Host`, `Origin` y `Sec-Fetch-Site`; envía cabeceras de seguridad (CSP, `X-Frame-Options`, `nosniff`); y devuelve 503 si el servicio destino no responde.

## 2.2 Autenticación (8101)

**Responsabilidad:** cuentas, contraseñas, sesiones, roles (`guest` y `admin`), perfiles de huéspedes, bloqueo por intentos fallidos y recuperación de contraseña.

**Qué no hace:** no envía correos. Publica eventos que entrega Notificaciones.

| Método y ruta | Uso | Respuestas |
|---|---|---|
| `POST /api/auth/register` | Crea la cuenta y abre la sesión | 201, 400, 409, 429 |
| `POST /api/auth/login` | Inicia sesión | 200, 401 (con intentos restantes), 429 |
| `GET /api/auth/me` | Usuario de la sesión, con su rol | 200, 401 |
| `POST /api/auth/logout` | Cierra y revoca la sesión | 200 |
| `POST /api/auth/forgot-password` | Envía un enlace de recuperación | 202 siempre, exista o no el correo |
| `POST /api/auth/reset-password` | Cambia la contraseña con el token | 200, 400 |
| `GET /api/guests` | Lista huéspedes (admin) | 200, 401, 403 |
| `POST /api/guests` | Crea un perfil de huésped (admin) | 201, 400, 403, 409 |
| `PATCH /api/guests/{id}` | Edita o reactiva (admin) | 200, 400, 403, 404 |
| `DELETE /api/guests/{id}` | Desactiva y revoca sus sesiones (admin) | 200, 403, 404 |

**Internas:** `GET /internal/users/{id}` devuelve nombre y correo para Notificaciones. `GET /auth/me` también lo usan los demás servicios para validar la sesión y el rol.

**Eventos que publica:** `welcome` al registrarse, `password.reset` al pedir recuperación y `password.changed` al cambiar la contraseña.

## 2.3 Notificaciones (8102)

**Responsabilidad:** recibir eventos, buscar el destinatario en Autenticación, guardar el mensaje y enviarlo por correo con reintentos.

**Qué no hace:** no acepta un correo destino enviado por el navegador. El destinatario siempre sale de Autenticación.

| Método y ruta | Uso | Respuestas |
|---|---|---|
| `GET /api/notifications` | Avisos del usuario de la sesión | 200, 401 |
| `POST /internal/events` | Recibe un evento (solo servicios) | 202, 200 si ya existía, 400, 403 |

**Envío:** `MAIL_PROVIDER=smtp` usa Gmail SMTP con TLS; `MAIL_PROVIDER=gmail_api` usa la API HTTPS de Gmail (necesaria en Render). Sin credenciales, el aviso queda como vista previa en la web. Un error se reintenta hasta cinco veces con espera creciente.

**Estados del mensaje:** `vista_previa`, `pendiente`, `reintentando`, `aceptado_smtp`, `aceptado_api`, `error`. Los correos de recuperación no se muestran en la bandeja web.

## 2.4 Reservas (8103)

**Responsabilidad:** crear, listar y cancelar reservas; calcular el total en el servidor; y coordinar con Inventario.

**Qué no hace:** no decide si hay cupo. Eso lo decide Inventario.

| Método y ruta | Uso | Respuestas |
|---|---|---|
| `POST /api/reservations` | Crea una reserva | 201 confirmada, 202 pendiente, 400, 401, 404, 409 sin cupo |
| `GET /api/reservations` | Reservas del usuario | 200, 401 |
| `POST /api/reservations/{id}/cancel` | Cancela una reserva propia; repetirla no cambia nada | 200, 202 cancelando, 401, 404 |

**Interna:** `POST /internal/reconcile` completa las reservas en Pendiente o Cancelando. La usa `start.py` al arrancar; además hay un hilo que lo hace cada 2 segundos.

**Eventos que publica:** `reservation.confirmed` y `reservation.cancelled`.

## 2.5 Catálogo de hoteles (8104)

**Responsabilidad:** datos del hotel: nombre, zona, dirección, descripción, servicios, comodidades, foto y créditos.

**Qué no hace:** no conoce habitaciones, precios ni ocupación.

| Método y ruta | Uso | Respuestas |
|---|---|---|
| `GET /api/hotels` | Hoteles activos | 200 |
| `GET /api/hotels/{id}` | Un hotel | 200, 404 |
| `POST /api/hotels` | Crea un hotel (admin) | 201, 400, 401, 403 |
| `PATCH /api/hotels/{id}` | Edita o reactiva (admin) | 200, 400, 403, 404 |
| `DELETE /api/hotels/{id}` | Retiro lógico (admin) | 200, 403, 404 |

`includeInactive=true` muestra también los retirados y solo lo puede usar un administrador.

## 2.6 Habitaciones (8105)

**Responsabilidad:** tipos de habitación de cada hotel con capacidad y tarifa por noche.

**Qué no hace:** no guarda cuántas unidades están ocupadas. Al crear un tipo, pide a Inventario que registre sus unidades.

| Método y ruta | Uso | Respuestas |
|---|---|---|
| `GET /api/rooms?hotelId=&guests=` | Tipos por hotel y capacidad mínima | 200, 400 |
| `GET /api/rooms/{id}` | Un tipo | 200, 404 |
| `POST /api/rooms` | Crea un tipo con sus unidades (admin) | 201, 202 si Inventario no respondió, 400, 403, 404 |
| `PATCH /api/rooms/{id}` | Edita nombre, capacidad, tarifa o estado (admin) | 200, 400, 403, 404 |
| `DELETE /api/rooms/{id}` | Retiro lógico (admin) | 200, 403, 404 |

Un tipo nuevo no se muestra al público hasta que Inventario confirma sus unidades (`inventory_ready`).

## 2.7 Disponibilidad e inventario (8106)

**Responsabilidad:** unidades por tipo de habitación, ocupación por fechas y asignación sin sobreventa.

| Método y ruta | Uso | Respuestas |
|---|---|---|
| `GET /api/inventory` | Unidades por tipo | 200 |
| `GET /api/availability?checkin=&checkout=` | Unidades libres por tipo en el rango | 200, 400 |
| `PUT /api/inventory/{roomId}` | Cambia las unidades (admin) | 200, 400, 403, 404, 409 si baja del pico de ocupación futura |

**Internas:**

- `POST /internal/allocate`: asigna una unidad a una reserva. Devuelve 409 si no hay cupo. Es idempotente por reserva.
- `POST /internal/release`: libera la unidad de una reserva.
- `POST /internal/inventory`: crea el inventario de un tipo nuevo (lo llama Habitaciones).

**Concurrencia:** en PostgreSQL usa un bloqueo asesor por reserva y un bloqueo de fila por habitación. Dos reservas simultáneas por la última unidad no pueden confirmarse ambas.

## 2.8 Códigos HTTP comunes

| Código | Significado en Hotels |
|---|---|
| 200 | Operación correcta |
| 201 | Recurso creado |
| 202 | Aceptado, pero queda pendiente de otro servicio |
| 400 | Datos inválidos; el mensaje explica cuál |
| 401 | No hay sesión o expiró |
| 403 | Sin permiso (rol, origen o clave interna) |
| 404 | No existe o pertenece a otro usuario |
| 405 | Método no permitido |
| 409 | Conflicto: correo repetido, sin cupo o estado incompatible |
| 413 | Cuerpo vacío o mayor de 16 KB |
| 415 | El cuerpo no es JSON |
| 429 | Demasiados intentos; incluye `Retry-After` |
| 503 | Un servicio necesario no responde |

Todas las respuestas de error tienen la forma `{"error": "mensaje en español"}`.
