# 9. Guion de sustentación

Sigue las diez etapas de la sección 6 de la guía. Sirve como base para las diapositivas y para ensayar. Los tiempos son una referencia para unos 20 minutos.

## Antes de empezar

- Iniciar Hotels 10 minutos antes con las bases Supabase y abrir `/status.html`: los seis servicios en **Activo**.
- Tener abiertas estas pestañas: la aplicación, `/status.html`, `/docs.html`, `/admin.html`, el repositorio en GitHub (pestaña Actions) y el panel de Supabase.
- Tener una cuenta administradora ya creada y una cuenta de huésped por crear en vivo, con un correo que se pueda abrir.
- Tener una terminal con Docker (`docker compose ps`) si se va a mostrar en vivo.
- **Plan B:** si falla internet o Supabase, vaciar las URL de base en `.env` y reiniciar. La aplicación funciona con SQLite local. Si falla la interfaz, ejecutar `python tools/demo_flujo.py`, que recorre el mismo flujo por la API.

## 1. Problema (1 minuto)

Reservar un hotel involucra partes que cambian a ritmos distintos: la información del hotel, los tipos de habitación y sus tarifas, la ocupación por noche, la reserva y la comunicación con el cliente. En un sistema monolítico, un fallo o un cambio en una parte afecta a todas, y dos personas pueden quedarse con la misma habitación si la ocupación no se controla bien.

**Contexto:** hoteles de Montería, Córdoba. Los hoteles son referencias públicas; las reservas no son reales.

## 2. Objetivo (1 minuto)

**General:** construir un sistema de reservas hoteleras con arquitectura de microservicios que permita consultar disponibilidad, registrar una reserva, actualizar el inventario y generar la confirmación.

**Específicos:**

1. Separar el sistema en seis microservicios, cada uno con su base PostgreSQL.
2. Exponer una API REST documentada con OpenAPI a través de un API Gateway.
3. Proteger el acceso con sesiones, roles de huésped y administrador, y bloqueo por intentos.
4. Comunicar los servicios por HTTP y, para los avisos, de forma asíncrona sin perder eventos.
5. Empaquetar la solución con Docker Compose y verificarla con pruebas automáticas en CI.

## 3. Arquitectura (2 minutos)

Mostrar el diagrama general de [01-arquitectura.md](01-arquitectura.md).

**Por qué microservicios:** cada dominio se despliega, falla y cambia por separado. Si Inventario se cae, se siguen consultando hoteles e iniciando sesión, y las reservas quedan pendientes en lugar de perderse.

## 4. Microservicios (3 minutos)

Mostrar la tabla de [02-microservicios.md](02-microservicios.md). Una frase por servicio, con lo que **no** hace:

- **Autenticación:** cuentas, sesiones, roles y recuperación. Único servicio que guarda correos y contraseñas.
- **Catálogo:** datos del hotel. No sabe de precios.
- **Habitaciones:** tipos, capacidad y tarifa. No sabe si están ocupadas.
- **Disponibilidad e inventario:** unidades y ocupación por noche. No sabe de usuarios.
- **Reservas:** coordina a los anteriores y guarda el estado de la reserva.
- **Notificaciones:** convierte eventos en correos.

Abrir `/docs.html` y mostrar Swagger con el contrato público y el interno.

## 5. Comunicación (2 minutos)

Mostrar el diagrama de comunicación y el de secuencia de la reserva.

- **Síncrona:** HTTP con JSON y la cabecera `X-Internal-Key`. Ejemplo: Reservas pide la tarifa a Habitaciones; Habitaciones pide a Inventario que cree las unidades de un tipo nuevo.
- **Asíncrona:** patrón outbox. El evento se guarda junto con la reserva y un hilo lo entrega a Notificaciones con reintentos. Explicar por qué no RabbitMQ (D6 en [04-decisiones-tecnicas.md](04-decisiones-tecnicas.md)).

## 6. Persistencia (2 minutos)

Mostrar [03-modelo-de-datos.md](03-modelo-de-datos.md).

- Una base por servicio: seis proyectos PostgreSQL distintos en Supabase.
- No hay claves foráneas entre servicios; las referencias se validan por API.
- Abrir el panel de Supabase y mostrar que son proyectos distintos, con esquema privado y RLS.

## 7. Seguridad (2 minutos)

Ver [05-seguridad.md](05-seguridad.md). En vivo:

1. `GET /api/reservations` sin sesión en Swagger: 401.
2. Herramientas del navegador: la cookie `hotels_session` es `HttpOnly`.
3. Contraseña incorrecta: muestra los intentos restantes.
4. Con la cuenta de huésped, abrir `/admin.html`: "Acceso restringido".
5. En Supabase: la tabla `users` muestra el hash, no la contraseña.

## 8. Contenedores (2 minutos)

- Mostrar `Dockerfile` y `compose.yaml`: siete contenedores, un solo Dockerfile, solo el Gateway publica puerto, cada contenedor con su `healthcheck`.
- Mostrar `docker compose ps` con los contenedores en `healthy`, o el trabajo **Docker Compose** en verde en GitHub Actions.
- Mencionar `render.yaml` y `vercel.ts`: la misma imagen está preparada para desplegarse por servicio.

## 9. Pruebas (2 minutos)

- Mostrar [07-plan-de-pruebas.md](07-plan-de-pruebas.md): 121 comprobaciones de integración, más configuración, migración, contratos, correo, nube, frontend y Docker.
- Mostrar la pestaña Actions de GitHub con los cuatro trabajos en verde.
- Mencionar la ejecución con las seis bases reales (`--six-postgres`).
- Opcional en vivo: `python tests/integration.py` (tarda alrededor de un minuto).

## 10. Demostración (4 minutos)

Flujo completo que atraviesa los seis servicios:

| Paso | Acción | Servicios que intervienen |
|---|---|---|
| 1 | Abrir `/status.html` | Gateway y los seis `/health` |
| 2 | Registrarse con una cuenta nueva | Autenticación, y Notificaciones por outbox |
| 3 | Buscar fechas y huéspedes | Catálogo, Habitaciones, Inventario |
| 4 | Elegir habitación y ver el total | Habitaciones |
| 5 | Confirmar la reserva | Reservas, Autenticación, Habitaciones, Catálogo, Inventario |
| 6 | Ver que esa habitación ya no tiene cupo en esas fechas | Inventario |
| 7 | Abrir la campana: bienvenida y confirmación | Notificaciones, Autenticación |
| 8 | Mostrar el correo recibido en Gmail | Notificaciones |
| 9 | Cancelar la reserva | Reservas, Inventario, Notificaciones |
| 10 | Con la cuenta admin, crear una habitación en `/admin.html` | Habitaciones, Catálogo, Inventario |
| 11 | Mostrar en la consola los logs de cada servicio | Todos |

**Tolerancia a fallos (opcional, 1 minuto, con Docker):**

1. `docker compose stop availability`
2. `/status.html` muestra Inventario "Sin respuesta".
3. Reservar: queda **Pendiente** (202).
4. `docker compose start availability`
5. En unos segundos la reserva pasa sola a **Confirmada**.

## Preguntas probables

| Pregunta | Respuesta corta |
|---|---|
| ¿Por qué no JWT? | Revocación inmediata al cerrar sesión, cambiar contraseña o desactivar un huésped; la cookie no es legible desde JavaScript. Ver D5 |
| ¿Por qué no RabbitMQ? | Un solo consumidor; la outbox garantiza que no se pierden eventos sin operar otro componente. Ver D6 |
| ¿Qué pasa si se cae un servicio? | El resto sigue. Si es Inventario, la reserva queda Pendiente y se completa sola |
| ¿Cómo evitan reservar dos veces la misma habitación? | Inventario asigna dentro de una transacción con bloqueo asesor y bloqueo de fila. Hay pruebas con dos procesos a la vez |
| ¿Cómo se comunican si no comparten base? | Por API. Reservas guarda copia del nombre y el total para conservar el historial |
| ¿Quién puede cambiar hoteles y precios? | Solo una cuenta con rol admin. El rol se revisa en Auth en cada operación |
| ¿Cómo se crea un administrador? | Un operador ejecuta `tools/set_admin.py`. El registro público no acepta roles |
| ¿Está publicado en internet? | La configuración de Vercel y Render está lista; falta conectar las cuentas |
| ¿Dónde están los pagos? | No se implementaron; no son necesarios para el flujo pedido |
