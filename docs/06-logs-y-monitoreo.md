# 6. Logs y monitoreo

## 6.1 Logs

Cada microservicio escribe una línea por petición en la salida estándar, con fecha, nivel, nombre del servicio, método, ruta sin parámetros y código HTTP:

```text
2026-11-02 21:23:43,010 INFO autenticacion POST /auth/register 201
2026-11-02 21:23:43,085 INFO disponibilidad-inventario GET /availability 200
2026-11-02 21:23:43,212 INFO disponibilidad-inventario POST /internal/allocate 201
```

El Gateway registra el acceso HTTP completo que recibe del navegador:

```text
127.0.0.1 - - [02/Nov/2026 21:23:43] "POST /api/auth/register HTTP/1.1" 201 -
```

**Nombres en los logs:** `autenticacion`, `notificaciones`, `reservas`, `catalogo-hoteles`, `habitaciones`, `disponibilidad-inventario`.

**Qué no se registra:** cuerpos de petición, cookies, contraseñas, tokens ni correos. Por eso la ruta se escribe sin la cadena de consulta.

**Errores:** una excepción no controlada se registra con `logging.exception` y el nombre del servicio, y el cliente recibe un 500 genérico sin detalles internos. También se registran los fallos de la outbox, del envío de correo y de las altas de inventario pendientes.

**Dónde verlos:**

- Local: en la consola donde corre `INICIAR.cmd` o `start.py`. Los siete procesos escriben en la misma ventana.
- Docker: `docker compose logs -f` o `docker compose logs -f reservations` para uno solo.
- Render: la pestaña Logs de cada servicio.

Un ejemplo real del flujo completo está en [evidencias/logs-flujo-demo.txt](evidencias/logs-flujo-demo.txt). Se ve cómo una sola reserva genera llamadas a Autenticación, Habitaciones, Catálogo, Inventario y después Notificaciones.

## 6.2 Salud de cada servicio

Cada proceso responde `GET /health`:

```json
{"status": "ok", "service": "reservas", "database": "postgresql"}
```

- Comprueba la conexión a su base con `SELECT 1`. Si falla, responde 503.
- `database` dice si el servicio está usando PostgreSQL o SQLite.
- Reservas responde 503 con `status: migrating` mientras quedan reservas antiguas sin sincronizar con Inventario.

## 6.3 Estado general

- `GET /api/readiness` en el Gateway consulta los seis `/health` y devuelve `ready: true` solo si todos responden.
- `http://127.0.0.1:8080/status.html` muestra esa información en una tabla que se actualiza cada 5 segundos. Si se detiene un servicio, su fila pasa a "Sin respuesta" en el siguiente ciclo. Es útil para mostrar el monitoreo en la sustentación.

Captura: [evidencias/04-estado-servicios.jpg](evidencias/04-estado-servicios.jpg).

## 6.4 Contenedores y nube

- En `compose.yaml`, cada contenedor tiene `healthcheck` sobre su `/health` cada 10 segundos. `docker compose ps` muestra `healthy` o `unhealthy`.
- En `render.yaml`, cada servicio declara `healthCheckPath: /health`; Render reinicia el que no responde.
- `start.py` espera el `/health` de los seis servicios antes de abrir el Gateway.

## 6.5 Recuperación automática

| Situación | Qué se ve | Qué hace el sistema |
|---|---|---|
| Inventario caído al reservar | Reserva en `Pendiente`, respuesta 202 | El reconciliador de Reservas reintenta cada 2 segundos |
| Inventario caído al cancelar | Reserva en `Cancelando` | El reconciliador completa la liberación |
| Notificaciones caído | Evento sin entregar en la outbox | La outbox reintenta con espera creciente, hasta 60 s entre intentos |
| Gmail rechaza el envío | Aviso en "Reintentando entrega" | Hasta cinco intentos con espera creciente (15 s a 5 min) |
| Inventario caído al crear habitación | Habitación con `inventory_ready = 0`, respuesta 202 | Habitaciones reintenta cada 3 segundos |

## 6.6 Límites

No hay métricas agregadas (Prometheus, Grafana) ni trazas distribuidas. Para la escala del proyecto se usan logs por servicio, `/health`, `/api/readiness` y la página de estado. Una mejora posible es añadir un identificador de petición que el Gateway propague a los servicios para seguir una operación entre logs.
