# 4. Decisiones técnicas y tecnologías

## 4.1 Tecnologías usadas

| Capa | Tecnología | Uso |
|---|---|---|
| Frontend | HTML, CSS y JavaScript del navegador | Páginas de huésped, panel admin, estado y Swagger |
| Backend | Python 3.12, biblioteca estándar (`http.server`, `urllib`, `threading`, `hashlib`, `logging`) | Gateway y seis microservicios |
| Base de datos | PostgreSQL en Supabase (seis proyectos), driver `psycopg 3.3.6` | Una base por servicio |
| Base local y pruebas | SQLite | Alternativa cuando no hay URL de PostgreSQL |
| Contratos | OpenAPI 3.1 (YAML) y Swagger UI 5.34.0 | Documentación y pruebas manuales de la API |
| Correo | Gmail por SMTP con TLS o Gmail API por HTTPS | Envío desde Notificaciones |
| Contenedores | Docker (`python:3.12-slim`) y Docker Compose | Siete contenedores, uno por proceso |
| Calidad | GitHub Actions, pre-commit, ruff, ESLint | CI en cada pull request y en `main` |
| Nube | Vercel para el frontend, Render para el Gateway y los seis servicios (plan gratuito) | `vercel.ts`, `render.yaml`, https://hotels-monteria-dodyce.vercel.app |
| Versionado | Git y GitHub (`DodyCe/hotels`), una rama por tema y pull requests | Historial del proyecto |

**No se usan:** frameworks web (Flask, FastAPI, Django), ORM, React, RabbitMQ, Kafka, Kubernetes ni pagos. No se deben presentar como parte del proyecto.

## 4.2 Decisiones

### D1. Seis microservicios por dominio

**Decisión:** separar Autenticación, Notificaciones, Reservas, Catálogo, Habitaciones y Disponibilidad e inventario.

**Razón:** cada uno tiene datos y reglas propias. El hotel cambia poco; la tarifa cambia por tipo; la ocupación cambia con cada reserva; la identidad y los correos son transversales. Separarlos evita que un cambio en uno obligue a tocar los otros. Supera el mínimo de cinco que pide la guía.

**Costo:** más llamadas entre servicios y más configuración.

### D2. Python con la biblioteca estándar

**Decisión:** no usar framework web. Cada servicio hereda de un `Handler` común sobre `http.server`.

**Razón:** pocas dependencias (solo `psycopg` y `PyYAML`), arranque rápido y código que se puede leer completo en la sustentación. Se ve directamente cómo se valida, cómo se responde y cómo se llama a otro servicio.

**Costo:** hay que escribir a mano la validación y el enrutamiento que un framework daría hecho.

### D3. Gateway propio

**Decisión:** un `gateway.py` en lugar de Nginx, Kong u otro producto.

**Razón:** enrutar, servir el frontend, publicar los contratos y verificar origen y host son reglas cortas. Un producto aparte añadiría configuración sin aportar a la demostración.

### D4. Una base PostgreSQL por servicio, en proyectos separados

**Decisión:** seis proyectos Supabase, uno por servicio, cada uno con esquema privado, RLS y un rol técnico sin permisos administrativos.

**Razón:** es lo que pide la guía y evita el atajo de usar seis esquemas de una misma base. Cada servicio solo recibe su propia cadena de conexión. `hotels_meta.service_owner` impide inicializar un servicio sobre la base de otro.

**Costo:** no hay JOIN ni claves foráneas entre dominios. Las referencias se validan por API y Reservas guarda copias históricas (nombre del hotel, total).

### D5. Sesiones opacas en lugar de JWT

**Decisión:** al iniciar sesión, Auth genera un token aleatorio, guarda su hash SHA-256 y lo entrega en una cookie `HttpOnly`, `SameSite=Strict`, de ocho horas. Los demás servicios validan la sesión con `GET /auth/me`.

**Razón:** cerrar sesión, cambiar la contraseña o desactivar a un huésped revoca el acceso al instante. Con JWT habría que esperar a que el token venza o mantener una lista de revocados. La cookie `HttpOnly` impide que JavaScript lea el token.

**Costo:** cada operación protegida hace una llamada a Auth. Para esta escala no es un problema. La guía acepta "otro mecanismo justificado"; JWT queda como evolución si se separan los servicios en redes distintas.

### D6. Patrón outbox en lugar de RabbitMQ o Kafka

**Decisión:** los eventos (bienvenida, recuperación, confirmación, cancelación) se guardan en una tabla `outbox` en la misma transacción que el cambio de negocio. Un hilo los entrega por HTTP a Notificaciones y reintenta si falla. Notificaciones descarta duplicados por el id del evento.

**Razón:** garantiza que el evento no se pierde si la reserva se guardó, aunque Notificaciones esté caído, sin operar un broker más. La guía permite "u otra tecnología".

**Costo:** no hay colas con varios consumidores ni enrutamiento por temas. Si se necesitaran, la outbox puede publicar en RabbitMQ sin cambiar el resto.

### D7. Estados recuperables en reservas

**Decisión:** la reserva pasa por `Pendiente` y `Cancelando` antes de quedar `Confirmada` o `Cancelada`. Un reconciliador termina las que quedaron a mitad.

**Razón:** si Inventario se cae durante una reserva, el sistema no queda inconsistente ni pierde la solicitud. Las pruebas detienen Inventario a propósito para comprobarlo.

### D8. El precio lo calcula el servidor

**Decisión:** Reservas pide la tarifa a Habitaciones y calcula noches por tarifa. Ignora cualquier total enviado por el navegador.

**Razón:** evita que alguien modifique el precio desde las herramientas del navegador.

### D9. Clave interna entre servicios

**Decisión:** toda llamada entre servicios lleva `X-Internal-Key`, una clave de al menos 32 caracteres que el navegador nunca recibe. Las rutas `/internal/*` la exigen.

**Razón:** un usuario no puede llamar directamente a `/internal/allocate` para ocupar cupos ni a `/internal/users/{id}` para leer correos.

### D10. Administración por rol, sin auto-registro de administradores

**Decisión:** el registro público siempre crea `guest`. Un operador promueve una cuenta con `python tools/set_admin.py --email ...`, lo que revoca sus sesiones anteriores.

**Razón:** ningún dato enviado desde el navegador puede convertir a alguien en administrador. Cada servicio vuelve a preguntar el rol a Auth en cada operación.

### D11. Retiro lógico

**Decisión:** `DELETE` en hoteles, habitaciones y huéspedes marca `active = 0`; no borra la fila.

**Razón:** las reservas antiguas siguen apuntando a esos registros, y se puede reactivar desde el panel.

### D12. Frontend sin framework

**Decisión:** HTML, CSS y JavaScript del navegador.

**Razón:** el foco de la materia es el backend distribuido. La web se sirve como archivos estáticos desde el Gateway o desde Vercel sin paso de compilación obligatorio.

### D13. Monorepositorio

**Decisión:** un solo repositorio con los siete procesos, migraciones, contratos y pruebas.

**Razón:** se revisan en un mismo pull request el cambio de un servicio, su contrato y su prueba. Compartir repositorio no implica compartir proceso ni base: cada servicio corre y se despliega por separado (ver `compose.yaml` y `render.yaml`).

### D14. Gmail API además de SMTP

**Decisión:** `MAIL_PROVIDER` permite elegir SMTP o la API HTTPS de Gmail.

**Razón:** el plan gratuito de Render bloquea los puertos SMTP. Con la API el correo sale por HTTPS.

## 4.3 Alternativas evaluadas

| Tema | Elegido | Alternativa | Por qué no |
|---|---|---|---|
| Autenticación | Sesión opaca en cookie | JWT | Revocación inmediata sin lista negra; cookie no accesible desde JavaScript |
| Mensajería | Outbox + HTTP | RabbitMQ, Kafka | Un broker más que operar; la outbox ya da entrega garantizada con reintentos |
| Gateway | `gateway.py` | Nginx, Kong | Las reglas son pocas y así se controlan origen, contratos y frontend en un solo lugar |
| Framework | Biblioteca estándar | FastAPI, Flask | Menos dependencias y código explicable línea por línea |
| Bases | Seis proyectos Supabase | Una base con seis esquemas | No sería una base por servicio real |
| Frontend | HTML/CSS/JS | React | No aporta a los criterios de la materia y añade compilación |
| Pagos | No incluidos | Pasarela de pago | Fuera del alcance acordado; el total se muestra pero no se cobra |
