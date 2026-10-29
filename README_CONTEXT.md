# Hotels — contexto completo del proyecto

Actualizado el **28 de octubre de 2026**. Este es el documento central de contexto, funcionamiento, herramientas, decisiones, verificación e historial de Hotels. Reúne la información antes distribuida en `HISTORIAL_PROYECTO.md`, `DECISIONES_TECNICAS.md`, `PRUEBAS.md`, `SUPABASE.md` y `FUENTES.md`.

Los resultados de ejecución que se citan conservan sus fechas. Tener código escrito, un proveedor configurado o un commit publicado no significa haber completado un despliegue público ni todos los entregables.

## 1. Objetivo y guía

Hotels desarrolla el **proyecto 6: Sistema de Reservas Hoteleras**, de la guía `PROYECTO FINAL_mivcroservicios GRUPO 11-2.docx`. La guía original se conserva en la carpeta `optativa`; no es un archivo del funcionamiento de la web. Se leyó completa y se exportó una copia temporal de nueve páginas a PDF para revisar también las secciones finales. El original no se modificó.

El flujo central es consultar hoteles y habitaciones, buscar disponibilidad por fechas y huéspedes, iniciar sesión, reservar, asignar inventario, confirmar, consultar/cancelar la reserva y generar avisos para el correo de la cuenta.

Se requiere un mínimo de cinco microservicios. Se implementaron **seis servicios de negocio**, además del Gateway. El trabajo debe verse como un producto coherente: nombre Hotels, textos profesionales y decisiones con una razón documentada. Los establecimientos son referencias informativas independientes; las operaciones aquí no constituyen reservas emitidas por esos hoteles.

## 2. Ubicación y archivos que deben conservarse

La carpeta activa, trasladada por el usuario, es:

```text
C:\Users\DODY\OneDrive\Escritorio\optativa\hotels
```

La ubicación anterior era `C:\Users\DODY\Documents\Codex\2026-10-15\rev\outputs\hotels`. Ya no debe usarse como ruta del código activo. Los ZIP, capturas y boceto de la antigua carpeta `outputs` eran entregas/intermedios anteriores; la web actual no los carga.

```text
hotels/
  README.md                 Entrada breve en GitHub
  README_CONTEXT.md         Contexto y documentación consolidados
  INICIAR.cmd               Iniciador para Windows
  start.py                  Arranque y coordinación de los procesos
  gateway.py                Servidor web y entrada de las APIs
  requirements.txt          Dependencia PostgreSQL fijada
  Dockerfile, compose.yaml  Definición de contenedores
  .env.example              Plantilla sin secretos
  .env                      Configuración privada local, fuera de Git
  .git/                     Historial real del repositorio
  .venv/                    Entorno Python local, fuera de Git
  web/                      HTML, CSS y JavaScript del frontend
  services/                 Código de los seis microservicios y utilidades
  seed/                     Datos iniciales de hoteles, habitaciones e inventario
  migrations/               SQL de Auth, Notificaciones, Catálogo y Habitaciones
  tools/                    Comprobación SMTP y migración de datos
  tests/                    Pruebas ejecutables del proyecto
  docs/openapi.yaml         Especificación OpenAPI 3.1 de la API pública
  .github/workflows/ci.yml  Integración continua: lint, pruebas y frontend
  requirements-dev.txt      Herramientas de desarrollo Python (ruff, pre-commit)
  package.json              ESLint para el frontend (solo desarrollo)
  data/                     Bases SQLite, clave interna y respaldos privados
```

`tests/` contiene código útil para futuras comprobaciones. No es lo mismo que el antiguo informe repetido `PRUEBAS.md`. Tampoco son basura `.env`, `.git`, `.venv`, las semillas, migraciones ni los respaldos de las bases. Los archivos `web/styles.css` y `web/hotels.css` se cargan juntos y se conservan.

## 3. Tecnologías y herramientas utilizadas

- **Frontend:** HTML5, CSS y JavaScript del navegador, sin React, Angular ni un framework de frontend. `web/index.html` estructura la página; `web/styles.css` y `web/hotels.css` definen la presentación; `web/app.js` consume las APIs; `web/catalog.js` permite una vista de diseño sin servidor.
- **Backend:** Python 3.12 o superior. Se utilizó Python 3.12.14 en las verificaciones iniciales. Los procesos usan principalmente la biblioteca estándar: `http.server`, `urllib`, `sqlite3`, `threading`, `logging`, `hashlib`, `secrets`, `smtplib`, `ssl` y `email.message`.
- **PostgreSQL:** `psycopg[binary]==3.3.6`, fijado en `requirements.txt`. No se usan el SDK ni el producto Supabase Auth para autenticar a los usuarios de Hotels.
- **Persistencia:** cuatro proyectos PostgreSQL independientes en Supabase y dos bases SQLite activas, una por servicio restante. JSON se usa para las semillas y los mensajes de API.
- **Correo:** Gmail SMTP configurable, TLS y contraseña de aplicación de una cuenta dedicada a Hotels. El correo lo envía Notificaciones; Supabase almacena datos.
- **Contenedores:** `Dockerfile` basado en `python:3.12-slim` y Docker Compose con un componente por proceso. Se escribieron las definiciones; su ejecución sigue pendiente de validación.
- **Control de versiones:** Git y el repositorio público [DodyCe/hotels](https://github.com/DodyCe/hotels). Se utilizó la CLI para revisar cambios, crear commits, subirlos y comparar el HEAD local/remoto. Desde el 28 de octubre los cambios se trabajan en ramas por tema y entran a `main` mediante pull requests, creados y fusionados con GitHub CLI (`gh`).
- **Entorno de desarrollo:** Windows, PowerShell, entorno Python `.venv` y Codex para edición, inspección, ejecución de comandos, revisión en navegador y consulta de documentación. Se utilizó el Python incluido en el entorno de Codex cuando correspondía.
- **Node.js:** se utilizó `node --check web/app.js` para comprobar sintaxis; no es el servidor de esta aplicación ni implica un backend Node/Express.
- **Revisión de la guía y evidencias:** Microsoft Word para exportar la guía de DOCX a PDF; herramientas Python y capturas de navegador para revisar texto, páginas y comportamiento. Esos archivos de trabajo no son dependencias de ejecución de Hotels.
- **Material visual:** imágenes remotas de Unsplash y fuentes de Google Fonts. Requieren conexión a internet. Los créditos y enlaces se conservan en la interfaz y en la sección de referencias de este documento.

No están implementados pagos, Kafka, RabbitMQ, Kubernetes ni una integración comercial con los hoteles. No se deben anunciar como tecnologías utilizadas.

## 4. Arquitectura y comunicación

**Frontend → API Gateway → microservicio → su propia base de datos.** Las respuestas al frontend regresan por el Gateway. Los seis microservicios y el Gateway forman el backend; no existe otro servidor adicional denominado «backend» que deba contenerlos.

El navegador usa rutas `/api` en el mismo origen. El Gateway, en 8080, sirve también la web y reenvía cada solicitud al dominio correspondiente. Los servicios internos pueden llamarse directamente por API; no necesitan atravesar el Gateway para cada comunicación entre ellos. Los endpoints internos requieren una clave que no recibe el frontend.

```mermaid
flowchart LR
  F[Frontend] --> G[API Gateway 8080]
  G --> A[Autenticación 8101]
  G --> N[Notificaciones 8102]
  G --> R[Reservas 8103]
  G --> C[Catálogo 8104]
  G --> H[Habitaciones 8105]
  G --> I[Disponibilidad e inventario 8106]
  A --> DA[(PostgreSQL Auth)]
  N --> DN[(PostgreSQL Notificaciones)]
  R --> DR[(SQLite Reservas)]
  C --> DC[(PostgreSQL Catálogo)]
  H --> DH[(PostgreSQL Habitaciones)]
  I --> DI[(SQLite Inventario)]
  R -->|Hotel, habitación y cupo por API| C
  R --> H
  R --> I
  R -->|Validar sesión| A
  A -->|Evento de bienvenida| N
  R -->|Evento de confirmación o cancelación| N
  N -->|Obtener destinatario| A
  N -->|SMTP con TLS| M[Proveedor de correo]
```

Este esquema ayuda a explicar el sistema. Los diagramas formales de arquitectura y de comunicación solicitados por la guía todavía deben prepararse y revisarse como entregables.

## 5. Microservicios y propiedad de los datos

1. **Autenticación — 8101 — `services/auth.py`.** Registra cuentas, valida contraseñas, crea/revoca sesiones y conserva el correo del usuario. Usa el proyecto PostgreSQL `hotels-auth`: esquema privado `hotels_auth`, tablas `users`, `sessions` y `outbox`.
2. **Notificaciones — 8102 — `services/notifications.py`.** Recibe eventos, obtiene el destinatario en Auth, guarda mensajes y gestiona SMTP y reintentos. Usa otro proyecto PostgreSQL, `hotels-notifications`: esquema privado `hotels_notifications`, tabla `messages`.
3. **Reservas — 8103 — `services/reservations.py`.** Guarda propietario, habitación, fechas, huéspedes, importe y estado de la operación, además de su outbox. Usa `data/reservations.sqlite3`.
4. **Catálogo de hoteles — 8104 — `services/catalog.py`.** Guarda establecimientos, ubicación, descripciones, fuentes y créditos; la tabla `hotels` conserva documentos JSON. Usa PostgreSQL en `hotels-catalog`, esquema `hotels_catalog`, tabla `hotels`. Las habitaciones, tarifas y ocupaciones pertenecen a otros servicios.
5. **Habitaciones — 8105 — `services/rooms.py`.** Tabla `rooms`: identificador, hotel, nombre del tipo, capacidad y precio. Usa PostgreSQL en `hotels-rooms`, esquema `hotels_rooms`, tabla `rooms`.
6. **Disponibilidad e inventario — 8106 — `services/availability.py`.** Tablas `inventory` y `allocations`: unidades por tipo de habitación, ocupación por rango y estado de asignación/liberación. Usa `data/availability.sqlite3`.

Cada servicio tiene API, proceso y base propios. Ninguno consulta directamente tablas de otro. Los identificadores entre dominios se resuelven por API; no hay claves foráneas entre proyectos PostgreSQL. Reservas conserva nombres e importe históricos de la operación, aunque los datos de origen cambien.

Hay tres hoteles de referencia y seis tipos de habitación, dos por hotel. Cada tipo comienza con una unidad de inventario de ejemplo. Las semillas `seed/hotels.json`, `seed/rooms.json` y `seed/inventory.json` inicializan solo su servicio; cambiar una semilla no sobrescribe automáticamente registros existentes.

Los archivos anteriores `auth.sqlite3`, `notifications.sqlite3`, `catalog.sqlite3` y `rooms.sqlite3` se conservan en `data` junto con los respaldos; no son las bases activas cuando sus URL PostgreSQL están configuradas. Si una URL se deja vacía, ese servicio puede funcionar en SQLite. Una URL configurada e inválida provoca un error, no un cambio silencioso de base.

## 6. Razones de las decisiones

- **Seis dominios:** separar los datos del hotel, características de la habitación, ocupación, transacción, identidad y entrega de mensajes evita mezclar responsabilidades y cumple el mínimo de la guía.
- **Una base por servicio:** cada dominio controla sus tablas y evolución. Las cuatro bases remotas están en proyectos físicamente separados, no en dos esquemas de una misma base presentada como dos bases independientes.
- **Monorepositorio:** facilita revisar contratos, semillas y pruebas coordinadas. Compartir repositorio o una máquina no obliga a compartir proceso ni base. Un único `start.py` sirve para desarrollo, pero no demuestra despliegues independientes.
- **Gateway:** ofrece una sola entrada para el navegador, enruta las APIs y controla hosts/origen sin entregar la clave interna al frontend. Cada servicio sigue comprobando las autorizaciones de su dominio.
- **Sesiones opacas:** permiten revocación inmediata y un flujo sencillo con cookies. Requieren consultar Auth para validar la sesión; se documentaron como alternativa a JWT.
- **Outbox e idempotencia:** conservar el evento junto con el cambio de negocio permite reintentar sin perderlo cuando Notificaciones no responde. Se utiliza HTTP y trabajadores asíncronos, sin un broker adicional.
- **SMTP configurable:** permite cambiar de proveedor sin modificar la interfaz ni incluir secretos en el código. La cuenta dedicada evita mantener el correo personal como identidad del producto.
- **Dos proyectos Supabase primero:** se eligieron Auth y Notificaciones según la decisión del usuario y el límite gratuito de su cuenta en esa etapa. El 23 de octubre se migraron Catálogo y Habitaciones en una segunda cuenta del usuario. Reservas e Inventario siguen locales; su migración permanece pendiente.
- **Presentación profesional:** se retiraron etiquetas repetidas de «práctica» en los flujos principales, manteniendo la independencia de los hoteles y los créditos de las imágenes. Un cambio de textos no convierte los datos de ejemplo en ofertas reales.

## 7. Seguridad implementada y JWT pendiente

Las contraseñas se guardan con **scrypt y sal aleatoria por usuario**, no como texto legible. El código usa `n=32768`, `r=8`, `p=1` y salida de 32 bytes. Las sesiones son tokens aleatorios de ocho horas: solo se guarda su hash SHA-256; cerrar sesión lo revoca. La cookie es `HttpOnly`, `SameSite=Strict` y admite `Secure` con `COOKIE_SECURE=1` para HTTPS.

Las APIs comprueban el propietario de reservas y avisos, y Auth limita intentos. Los errores y logs evitan mostrar contraseñas o cookies. El Gateway comprueba host y origen. Las credenciales PostgreSQL solo llegan al servicio dueño y las variables SMTP solo a Notificaciones.

Los proyectos Supabase tienen esquemas privados y tablas con RLS; las políticas de acceso se asignan a su rol técnico. `hotels_auth_app`, `hotels_notifications_app`, `hotels_catalog_app` y `hotels_rooms_app` tienen permisos limitados sobre su propio dominio; no pueden crear objetos, administrar roles ni omitir RLS. `hotels_meta.service_owner` impide inicializar un dominio sobre la base del otro. El aprovisionamiento utilizó verificadores SCRAM; las contraseñas quedan en `.env`.

**JWT todavía no está implementado.** El 22 de octubre se recomendó evaluarlo para el futuro despliegue distribuido: Auth firmaría con clave privada y los consumidores validarían con clave pública, comprobando firma, emisor, destinatario y vencimiento. Se necesitarían tokens de acceso cortos, renovación y revocación controladas, además de autorización en cada servicio. Esa conversación no fue una orden de sustituir las sesiones ni una implementación terminada.

Tampoco están implementadas la confirmación de titularidad del correo mediante un token, recuperación de contraseña, MFA ni todos los controles de una plataforma pública. El correo de bienvenida no verifica la propiedad de la dirección. HTTPS y cookies seguras deben configurarse y comprobarse al desplegar. JWT firmado no equivale a cifrar sus datos; nunca debe contener contraseñas.

`.env`, bases, respaldos, `.venv`, claves internas, caches y logs están excluidos de Git. No pegar contraseñas de Gmail o PostgreSQL, tokens ni cookies en este documento, el chat, capturas públicas o commits. No sobrescribir el `.env` actual con la plantilla.

## 8. Reservas, disponibilidad y eventos

Reservas obtiene por API la habitación y su tarifa, valida el hotel y capacidad, guarda la solicitud y pide una asignación a Inventario. El precio lo decide el servidor, no un importe enviado por JavaScript. Inventario verifica las noches en una transacción para evitar doble ocupación. La fecha de salida no ocupa noche; la llegada ese mismo día de otra reserva es válida.

Si Inventario no responde, la solicitud queda **Pendiente** y devuelve HTTP 202. Un trabajador reintenta para confirmarla o rechazarla por falta de cupos. Una cancelación interrumpida queda **Cancelando** y se completa al recuperar Inventario. El aviso corresponde a la transición confirmada. La liberación deja una marca que impide que una asignación tardía reactive una reserva cancelada.

Auth y Reservas guardan eventos en una outbox dentro de la transacción de negocio. Un trabajador los entrega por HTTP; Notificaciones deduplica por identificador de evento y obtiene el correo en Auth, sin confiar en un destinatario arbitrario del navegador. SMTP reintenta errores hasta cinco veces. No se promete entrega exactamente una vez cuando una conexión se pierde tras la aceptación del proveedor.

La migración de reservas anteriores conserva identificadores, importes, estado y propietario. Consulta hoteles/habitaciones por API y asigna cupos al tipo principal; una reserva cancelada no ocupa inventario ni reenvía sus avisos. El iniciador espera la reconciliación antes de abrir el Gateway.

## 9. Iniciar Hotels en Windows

Desde la carpeta activa ejecuta `INICIAR.cmd` y abre <http://127.0.0.1:8080/>. Mantén la consola abierta; `Ctrl+C` detiene los procesos. El iniciador utiliza `.venv` si existe y también reconoce otros Python instalados, incluido el del entorno de Codex.

Para iniciar manualmente:

```powershell
.\.venv\Scripts\python.exe start.py
```

En una instalación nueva con Python 3.12 o superior:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

El último comando es solo para una instalación sin `.env`; no reemplaza una configuración existente. Completa las conexiones privadas antes de iniciar. Abrir `web/index.html` directamente permite revisar el diseño, pero no activa cuentas, reservas o correo.

Si `127.0.0.1:8080` rechaza la conexión, comprueba que el iniciador siga abierto. El 22 de octubre ocurrió porque los procesos estaban detenidos; se iniciaron y se verificaron HTTP 200, salud de los seis servicios y el catálogo de tres hoteles. Esa verificación fue anterior al traslado de la carpeta. El 23 de octubre se inició la aplicación desde la nueva carpeta, con cuatro conexiones PostgreSQL. El estado de los procesos debe comprobarse de nuevo cuando se retome el trabajo.

## 10. Supabase: configuración y migración reproducible

Los dos primeros proyectos se crearon el 17 de octubre de 2026 en `dody's projects`, región `us-east-1`, con plan gratuito y sin complementos de pago. Son datos del aprovisionamiento registrado, no una garantía de condiciones futuras del proveedor.

- [hotels-auth](https://supabase.com/dashboard/project/abszvtlzemhccsiiwgqx), referencia `abszvtlzemhccsiiwgqx`, esquema `hotels_auth`.
- [hotels-notifications](https://supabase.com/dashboard/project/lhygyaadbiflclxeebxu), referencia `lhygyaadbiflclxeebxu`, esquema `hotels_notifications`.

El **23 de octubre**, en la organización gratuita `Dody` de la segunda cuenta, se aprovechó un proyecto vacío del usuario para Catálogo y se creó otro para Habitaciones, ambos en `us-east-1`:

- [hotels-catalog](https://supabase.com/dashboard/project/hliwjfyhbbmapjdlgltl), referencia `hliwjfyhbbmapjdlgltl`, esquema `hotels_catalog` y rol `hotels_catalog_app`.
- [hotels-rooms](https://supabase.com/dashboard/project/auumbmanspknomzueqhh), referencia `auumbmanspknomzueqhh`, esquema `hotels_rooms` y rol `hotels_rooms_app`.

El conector MCP seguía autorizado en la primera cuenta; la segunda se administró mediante el panel que abrió el usuario. Se comprobaron sus conexiones de sesión IPv4 en el propio panel, sin añadir IPv4 de pago. Los dos nuevos roles permiten SELECT e INSERT para consulta y migración inicial; no tienen UPDATE, DELETE, creación de objetos/roles ni bypass de RLS. Los esquemas no están expuestos a `anon` o `authenticated`. La Data API quedó desactivada al crear Habitaciones porque el backend usa PostgreSQL directamente.

Supabase había creado `public.rls_auto_enable()` como función administrativa con permisos públicos de ejecución. Se inspeccionó su definición y se revocó EXECUTE a PUBLIC, anon y authenticated, manteniendo el disparador automático de RLS. La corrección queda en los SQL de ambos servicios.

Las migraciones nuevas se generaron con **Supabase CLI 2.121.0**, obtenida del paquete oficial npm mediante `npx`, después de consultar `--help`. Los archivos `migrations/catalog/20261023072457_hotels_catalog_initial.sql` y `migrations/rooms/20261023072500_hotels_rooms_initial.sql` se aplicaron desde el editor SQL del panel, no mediante un `db push` ni un enlace del CLI a la cuenta. No contienen contraseñas; la activación de roles se hizo aparte con verificadores SCRAM. Los archivos privados de aprovisionamiento están bajo `data/provisioning`, fuera de Git y sin entregarse al navegador ni a otros servicios.

Se copiaron los tres hoteles y seis tipos existentes, manteniendo los identificadores, campos, tarifas y orden. PostgreSQL guarda `sort_order` porque no tiene el `rowid` de SQLite. Las APIs conservan el contrato: `hotelId` sigue teniendo esa capitalización y no se expone el campo interno de orden. No se crean claves foráneas entre las bases de Catálogo y Habitaciones.

Para reproducirlo en proyectos nuevos:

1. Aplica como administrador `001_initial.sql` y `002_backend_access.sql` de `migrations/auth/` o `migrations/notifications/` en el proyecto que corresponda. Para Catálogo y Habitaciones aplica el archivo con fecha de su carpeta correspondiente. Los scripts crean roles `NOLOGIN`; su activación y contraseña se aprovisionan por un canal privado administrativo. El rol de ejecución no hace DDL.
2. Copia la URI de **Connect → Session pooler**, con el host que muestre el panel, usuario técnico del proyecto y puerto de sesión 5432. No deduzcas el host solo de la región ni uses la URL HTTP, `anon` o una clave publicable como conexión PostgreSQL.
3. Completa `AUTH_DATABASE_URL`, `NOTIFICATIONS_DATABASE_URL`, `CATALOG_DATABASE_URL` y `ROOMS_DATABASE_URL` con sus conexiones diferentes y `sslmode=require`, codificando caracteres especiales de las contraseñas. Puede utilizarse `verify-full` con el certificado configurado. Son contraseñas de bases, no la contraseña de la cuenta Supabase.

```dotenv
AUTH_DATABASE_URL=postgresql://USUARIO_AUTH.REFERENCIA_AUTH:CONTRASENA_CODIFICADA@HOST_DEL_PANEL:5432/postgres?sslmode=require
NOTIFICATIONS_DATABASE_URL=postgresql://USUARIO_AVISOS.REFERENCIA_AVISOS:OTRA_CONTRASENA_CODIFICADA@HOST_DEL_PANEL:5432/postgres?sslmode=require
CATALOG_DATABASE_URL=postgresql://USUARIO_CATALOGO.REFERENCIA_CATALOGO:OTRA_CONTRASENA_CODIFICADA@HOST_DEL_PANEL:5432/postgres?sslmode=require
ROOMS_DATABASE_URL=postgresql://USUARIO_HABITACIONES.REFERENCIA_HABITACIONES:OTRA_CONTRASENA_CODIFICADA@HOST_DEL_PANEL:5432/postgres?sslmode=require
```

Para copiar datos de SQLite en una instalación que aún no se haya migrado, detén Hotels y ejecuta:

```powershell
.\.venv\Scripts\python.exe tools/migrate_supabase.py
.\.venv\Scripts\python.exe tools/migrate_supabase.py --apply
.\.venv\Scripts\python.exe tools/migrate_supabase.py
```

Para Catálogo y Habitaciones se seleccionan explícitamente los servicios:

```powershell
.\.venv\Scripts\python.exe tools/migrate_supabase.py --services catalog rooms
.\.venv\Scripts\python.exe tools/migrate_supabase.py --services catalog rooms --apply
.\.venv\Scripts\python.exe tools/migrate_supabase.py --services catalog rooms
```

El valor por defecto sigue siendo Auth/Notificaciones para conservar compatibilidad. La migración del 23 guardó respaldo en `data/backups/supabase-20261023T073307Z-edc6b020/` y comprobó cero pendientes en Catálogo y Habitaciones. Se respaldó también la configuración antes de añadir las dos conexiones; las de Auth, Notificaciones y Gmail se conservaron.

La comprobación sin `--apply` es de lectura. La copia respalda primero las SQLite en `data/backups/supabase-.../`, conserva identificadores, sales y hashes, copia solo sesiones vigentes y no elimina ni sobrescribe datos remotos. Una repetición conserva estados de entrega avanzados; un conflicto interrumpe la transacción. Cada proyecto tiene su propia transacción: no hay transacción distribuida entre los proyectos. La aplicación ya migrada no necesita repetir `--apply` al iniciar.

El respaldo de la migración del 17 de octubre quedó en `data/backups/supabase-20261017T173344Z-03aa7c6f/`. Se trasladaron los datos originales y se comprobó cero pendientes. Se corrigió un falso conflicto de fechas Unix usando lectura binaria en psycopg para evitar el redondeo textual de `extra_float_digits=0`. Los health de 8101 y 8102 deben mostrar `database: postgresql` cuando estén funcionando con esas conexiones.

## 11. Gmail y Notificaciones

Se implementaron bienvenida, confirmación y cancelación. Se probó inicialmente la configuración de cuenta y, después, se sustituyó el remitente por una cuenta dedicada a Hotels. El proveedor aceptó los mensajes de prueba y el usuario confirmó su recepción en Gmail. No es necesario documentar los correos personales ni las contraseñas usados durante la configuración.

Configuración privada de ejemplo:

```dotenv
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_SECURITY=starttls
SMTP_USER=tu-cuenta-del-proyecto@gmail.com
SMTP_PASSWORD=tu-contrasena-de-aplicacion
SMTP_FROM=tu-cuenta-del-proyecto@gmail.com
SMTP_TEST_TO=una-direccion-que-controles
```

Se valida TLS. Para un proveedor con puerto 465 se usa `SMTP_SECURITY=ssl`. Gmail requiere una contraseña de aplicación disponible para esa cuenta, no su contraseña normal ni un código temporal. Hubo dificultades de verificación con una cuenta nueva antes de completar la configuración; el envío finalmente quedó con la cuenta dedicada.

`python tools/test_smtp.py` comprueba campos sin enviar; `python tools/test_smtp.py --send` envía **un mensaje real** al destinatario configurado. Reinicia Hotels después de cambiar `.env`. Si falta configuración, los avisos quedan en vista previa dentro de la web; al habilitar SMTP no se reenvían automáticamente los antiguos. Cambiar textos tampoco reescribe mensajes históricos.

«Aceptado por el proveedor» no garantiza bandeja de entrada; hay que revisar recepción y spam. Sigue pendiente incorporar una captura de recepción como evidencia de entrega. Los logs no deben mostrar las credenciales.

## 12. API y respuestas

Todas las rutas usan JSON. El Gateway elimina `/api` al reenviar la solicitud:

- `GET /api/hotels` y `GET /api/hotels/{id}`: catálogo.
- `GET /api/rooms?hotelId={id}&guests=2` y `GET /api/rooms/{id}`: tipos, capacidad y tarifa; los filtros son opcionales.
- `GET /api/inventory`: unidades por tipo.
- `GET /api/availability?checkin=AAAA-MM-DD&checkout=AAAA-MM-DD`: disponibilidad por rango.
- `POST /api/auth/register`: `{name,email,password}`; cuenta, sesión y evento de bienvenida.
- `POST /api/auth/login`: `{email,password}`; `GET /api/auth/me`: perfil; `POST /api/auth/logout`: revocación.
- `POST /api/reservations`: `{roomId,checkin,checkout,guests}`; `hotelId` opcional debe coincidir con la habitación. Precio y propietario proceden del servidor.
- `GET /api/reservations`: reservas propias; `POST /api/reservations/{id}/cancel`: cancelación propia.
- `GET /api/notifications`: mensajes y estados propios.
- `GET /health` en cada proceso: salud básica; Reservas también informa de su preparación/migración.

`/internal/allocate`, `/internal/release`, `/internal/reconcile`, los eventos y las consultas internas de usuario son comunicación entre servicios, protegida con clave y sin rutas públicas equivalentes en el Gateway.

Estados relevantes: 202 pendiente, 400 datos inválidos, 401 sin sesión, 403 acceso no permitido, 404 recurso inexistente o ajeno, 409 conflicto, 429 exceso de intentos y 503 servicio no disponible. Los ejemplos de identificador incluyen `ghl-monteria-principal` y `ghl-monteria-alternativa`.

El contrato completo, con esquemas, parámetros, validaciones y códigos por ruta, está en [`docs/openapi.yaml`](docs/openapi.yaml) (OpenAPI 3.1). Puede abrirse en cualquier visor OpenAPI, por ejemplo el editor de Swagger. La web no sirve una interfaz Swagger: la CSP del Gateway solo permite scripts propios. `/auth/me` incluye `created`, la fecha de alta en segundos Unix. Catálogo y Habitaciones exponen consultas; no se implementó administración con permisos de edición ni un panel administrativo completo.

## 13. Pruebas y evidencia conservada

El 17 de octubre, antes de publicar los avances, se registraron **123 comprobaciones aprobadas**:

- 57 de integración con seis SQLite temporales.
- Otras 57 con dos PostgreSQL Supabase y cuatro SQLite temporales.
- Seis de configuración: separación física, identificación directa/pooler, configuración completa, TLS, errores sin contraseñas y credenciales por proceso.
- Tres de migración: respaldo y sesiones vigentes, repetición sin revertir entregas y rollback ante conflictos sin sobrescritura.

Las suites HTTP cubren registro/inicio/cierre de sesión, cookies, contraseñas derivadas, correo duplicado, orígenes rechazados, aislamiento por propietario, concurrencia por cupo, precio del servidor, filtrado y capacidad, fechas canónicas, migraciones antiguas, independencia de seis bases, reservas y cancelaciones idempotentes, avisos deduplicados y destinatario obtenido en Auth. También detienen/reinician Inventario para verificar **Pendiente → Confirmada** y **Cancelando → Cancelada**, y reinician Reservas para comprobar persistencia.

Los puertos de pruebas son 18080 y 18101–18106. SMTP está desactivado. La modalidad PostgreSQL crea cuentas únicas `example.test` y limpia sus cuentas/mensajes al terminar; no utiliza las reservas del usuario. Las comprobaciones SQL remotas iniciales usaron transacciones revertidas, y el asesor de seguridad de Supabase no informó observaciones tras configurar los roles. No son afirmaciones de auditoría permanente.

Para repetir las verificaciones:

```powershell
.\.venv\Scripts\python.exe tests/integration.py
.\.venv\Scripts\python.exe tests/database_config.py
.\.venv\Scripts\python.exe tests/migration.py
.\.venv\Scripts\python.exe tests/integration.py --postgres
node --check web/app.js
git diff --check
```

Se corrigió durante el desarrollo un bloqueo de archivos SQLite en Windows cerrando conexiones explícitamente. `node --check` y la revisión de whitespace pasaron en la actualización del 17. La revisión inicial en navegador incluyó cuenta, reserva, notificación, cancelación, cierre de sesión y carga de fotos; se observó un ancho móvil de 390 px sin desbordamiento. Una revisión visual completa de la versión final en escritorio y móvil sigue pendiente. Las capturas antiguas no demuestran que la versión actual esté validada.

Los resultados del 17 de octubre son históricos. En la consolidación documental del 22 no se repitieron las 123 comprobaciones; la actualización de código del 23 sí volvió a verificar ambas modalidades, como se detalla a continuación. No se ha validado carga, funcionamiento público ni contenedores. El SMTP real se comprobó aparte y el usuario confirmó llegada; no se enviaron correos nuevos como parte de esta limpieza.

### Verificación del 23 de octubre

- 57 comprobaciones de integración con todas las bases en SQLite temporal: aprobadas.
- Otras 57 con **cuatro PostgreSQL reales y dos SQLite temporales**, mediante `tests/integration.py --four-postgres`: aprobadas. Esta opción exige las cuatro conexiones y comprueba que no se crean SQLite de respaldo para esos dominios.
- Nueve pruebas de configuración y cinco de migración: aprobadas. Se añadieron casos de colisión entre proyectos, aislamiento de las cuatro conexiones, conservación del orden y de `hotelId`/tarifa y rechazo de conflictos.
- Total de las suites de esta actualización: **128 comprobaciones aprobadas**. SMTP desactivado y limpieza de las cuentas/mensajes temporales al terminar. No se enviaron nuevos correos reales.
- La migración verificó tres hoteles, seis habitaciones y cero pendientes; los roles se comprobaron sin permisos excesivos.
- Tras corregir la función de RLS, ambos paneles de Advisor Center quedaron sin observaciones de advertencia/error en sus filtros predeterminados. Se comprobaron también por SQL los esquemas privados, RLS y la ausencia de EXECUTE público sobre esa función.
- El arranque normal desde `optativa/hotels` respondió correctamente en los seis health: Auth, Notificaciones, Catálogo y Habitaciones indicaron `postgresql`; Reservas e Inventario continúan en SQLite. Las APIs del Gateway devolvieron tres hoteles y seis habitaciones. Las verificaciones no incluyen un despliegue de los procesos en la nube.

Para exigir las cuatro conexiones al repetir la integración:

```powershell
.\.venv\Scripts\python.exe tests/integration.py --four-postgres
```

### Verificación del 28 de octubre

- `tests/integration.py` en modo SQLite temporal, después de cada fusión: 57 de 57 comprobaciones aprobadas. `tests/migration.py`: 5 de 5.
- `tests/database_config.py` no se pudo completar en el equipo de esa sesión porque no tenía `psycopg` instalado. Falla la prueba que exige el driver; no se debe a los cambios.
- El frontend se revisó en navegador con la API simulada, a 390, 1024 y 1440 px. El reformateo de CSS/HTML conservó las 250 reglas CSS y la posición y los estilos calculados de los 260 elementos de la página.
- No se ejecutó la modalidad PostgreSQL ni `INICIAR.cmd` con los seis servicios, porque no había `.env` en ese equipo. Antes de entregar, conviene repetir `tests/integration.py --four-postgres` y revisar el flujo completo con las bases reales.

### Integración continua y revisión de código

GitHub Actions (`.github/workflows/ci.yml`) se ejecuta en cada pull request y en cada push a `main`. Tiene tres trabajos:

1. **Lint:** ejecuta pre-commit sobre todo el repositorio. Incluye `ruff` para Python, la validación de YAML y JSON, marcadores de conflicto, archivos grandes y claves privadas.
2. **Pruebas:** ejecuta `tests/integration.py` en SQLite temporal, `tests/database_config.py` y `tests/migration.py`. No usa las bases de Supabase ni el `.env`.
3. **Frontend:** ejecuta ESLint sobre `web/` y `node --check`.

Configuración:
- `ruff.toml` aplica las reglas de errores reales: nombres indefinidos, imports sin uso, comparaciones y excepciones. Respeta el estilo compacto del proyecto (`if x: return y`, `a(); b()`).
- `eslint.config.mjs` usa las reglas recomendadas con globales de navegador.
- `.editorconfig` fija UTF-8, LF y la indentación.

Para revisar localmente antes de subir:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\pre-commit.exe install
.\.venv\Scripts\ruff.exe check .
npm ci
npm run lint
```

Node solo se usa para ESLint; la web no depende de Node para funcionar. Las versiones de las herramientas están fijadas en `requirements-dev.txt`, `package.json` y `package-lock.json`.

## 14. Docker y alojamiento futuro

Se incluyen siete componentes en Compose: Gateway y seis servicios. Solo el Gateway publica un puerto al anfitrión; las SQLite usan volúmenes separados. Las conexiones PostgreSQL y SMTP se asignan únicamente a sus servicios correspondientes. La imagen ejecuta con un usuario sin privilegios.

Para una futura validación, configura una clave `INTERNAL_API_KEY` de al menos 32 caracteres, conserva las conexiones y ejecuta `docker compose up --build`; abre <http://127.0.0.1:8080/>. `docker compose down` detiene los contenedores; no usar opciones que eliminen volúmenes si se deben conservar los datos. **La ejecución de Docker está pendiente**, aunque los archivos existan.

El presupuesto acordado es gratuito. Tras migrar Catálogo y Habitaciones el 23 de octubre, quedan por migrar a bases remotas propias las SQLite de Reservas e Inventario. El destino será **frontend + Gateway + seis microservicios + seis bases independientes en la nube**. Subir únicamente las bases no aloja la aplicación completa.

Vercel se consideró para el frontend, con reescritura externa de `/api` hacia el Gateway para conservar el flujo del navegador; requerirá comprobar origen, hosts, HTTPS y cookies. Publicar HTML solo no habilita reservas.

En la evaluación del **17 de octubre**, Render gratuito no era compatible con el diseño actual: bloqueo de SMTP saliente por 25/465/587, archivos efímeros y ausencia de discos persistentes para las SQLite. También se registraron suspensión por inactividad y una cuota de horas compartida por el espacio de trabajo. Las condiciones del proveedor deben volver a comprobarse antes de elegir alojamiento; esa investigación no fue un despliegue ni una contratación. Un monorepositorio puede alimentar despliegues por servicio, pero ejecutar todo con `start.py` en una sola instancia no prueba independencia de despliegue.

**GitHub está autorizado para avances terminados y revisados; el despliegue público sigue pendiente.** No contratar planes ni crear recursos de pago. El proveedor definitivo del backend y de las dos bases restantes aún no está elegido.

## 15. Historial de avances

- **15 de octubre:** revisión del caso 6 y diseño inicial HTML/CSS/JS; evolución a Hotels, búsqueda de referencias de Montería y fotografías ilustrativas. Incorporación de cuentas, reservas y notificaciones, seguida de separación de Catálogo, Habitaciones e Inventario hasta completar seis dominios.
- **17 de octubre:** aprovisionamiento de dos PostgreSQL independientes en Supabase, roles privados, respaldo/migración, corrección de precisión de fechas, verificación de integración y Gmail dedicado con recepción confirmada por el usuario. Mejora de textos de producto y documentación de límites.
- Hubo una pausa de subidas para terminar desarrollo local; después se autorizó versionar avances en GitHub para conservar un historial. Esa autorización no incluía despliegue ni migración de las otras cuatro bases.
- **22 de octubre:** se restableció el servidor local detenido; se aclaró la ubicación de los archivos, diferencia entre bases locales/remotas, sesiones/JWT y función del Gateway. El usuario trasladó Hotels a `optativa` y solicitó consolidar documentación y retirar copias sobrantes.
- La documentación quedó centralizada en este archivo, con `README.md` como entrada breve. La orden de borrado fue bloqueada por la revisión automática de ejecución; se utilizó la alternativa autorizada de separar los sobrantes. Se movieron cinco documentos sustituidos y quince archivos de entregas anteriores (tres ZIP, cinco capturas y siete archivos del boceto) a `C:\Users\DODY\Documents\Codex\2026-10-15\rev\PARA_ELIMINAR_HOTELS_20261022`. La carpeta `outputs` antigua quedó vacía. No se borraron definitivamente esos archivos ni se trasladaron código activo, pruebas ejecutables, bases, respaldos o credenciales.

- **23 de octubre:** Catálogo y Habitaciones pasaron a dos PostgreSQL propios de la segunda cuenta. Se generaron migraciones, roles limitados, respaldos y conexiones privadas, se conservaron los datos y el contrato de API y se aprobaron 128 comprobaciones. Continúan seis microservicios, con cuatro bases remotas y dos locales; no se desplegaron los procesos en la nube.
- **28 de octubre:** se auditó el código y se integraron mejoras de frontend y documentación mediante los pull requests #1 a #8. Ningún cambio modifica el esquema de las bases ni rompe el contrato existente:
  - **Mantenimiento:** CSS e `index.html` formateados (antes estaban en líneas únicas) y Google Fonts cargado con `<link>` y `preconnect`.
  - **Experiencia de uso:**
    - Imagen principal con `srcset` y confirmación antes de cancelar una reserva.
    - Foco gestionado en los modales y estado de carga de la disponibilidad.
    - Avisos por tipo que se ven sobre el modal.
    - Destino como texto fijo, entrada animada del hero (respeta el movimiento reducido) y favicon en SVG y PNG.
    - Filtro de precio, resumen en «Mi cuenta», reservas agrupadas por estado y notificaciones con formato de correo.
    - Animaciones breves: entrada y salida del modal y de los avisos, resumen resaltado y total animado al elegir habitación, tarjetas que se elevan y aparecen al hacer scroll, y reacomodo con View Transitions al filtrar u ordenar. Todo se desactiva con «reducir movimiento» y no usa estilos en línea, para respetar la CSP.
  - **Correcciones:** el buscador calcula «hoy» con la hora de Montería, igual que el servidor; Notificaciones importa `hashlib` de forma normal; `/auth/me` agrega `created`.
  - **Documentación:** especificación OpenAPI en `docs/openapi.yaml`.
  - **Calidad:** integración continua en GitHub Actions, ruff, pre-commit, ESLint, `.editorconfig` y `requirements-dev.txt`. Ruff detectó un import sin uso en Notificaciones, que se eliminó.

Commits publicados y comprobados el 17 de octubre en `main`:

- `6af1ac1`: agregar Hotels con seis microservicios y pruebas de integración.
- `7c1d224`: conectar Auth y Notificaciones a bases Supabase independientes.
- `1ecdce2`: pulir textos de Hotels y sus flujos de reserva.
- `95859e5`: documentar historial, decisiones y pruebas del proyecto.

Los commits conservan el historial real, incluidas versiones anteriores de la documentación. Se pueden consultar con `git log --oneline`. Este documento no inventa fechas de ejecución o despliegues ni sustituye ese historial.

## 16. Entregables y pendientes de la guía

La sección final de entregables pide: código fuente; repositorio e historial Git; README; Docker Compose; Swagger/OpenAPI; diagrama general de arquitectura; diagrama de comunicación; modelo de datos por servicio; decisiones técnicas; plan y evidencias de pruebas; manual breve de instalación/uso; presentación; y demostración funcional.

Este documento reúne contexto y material útil para varios de ellos; **no completa automáticamente la entrega formal**. Falta:

1. Revisar el frontend con los servicios y las bases reales. El 28 de octubre se mejoraron estados de carga, errores, foco y presentación en escritorio y móvil, pero se probaron con la API simulada.
2. Revisar el alcance de administración de hoteles, habitaciones y huéspedes respecto de la guía; las consultas actuales no son un CRUD administrativo completo.
3. Elaborar los modelos de datos formales por servicio. La especificación OpenAPI ya está en `docs/openapi.yaml`.
4. Preparar los dos diagramas solicitados y el documento final con decisiones, seguridad y comunicación asíncrona justificadas.
5. Ejecutar y verificar Docker Compose y reproducibilidad en otra instalación.
6. Capturar evidencias actuales y correo recibido, completar manual, presentación y demostración integral.
7. Implementar, cuando se autorice, confirmación de correo y recuperación de contraseña; evaluar JWT antes de modificar la autenticación.
8. Migrar las dos bases restantes, Reservas e Inventario, y seleccionar alojamiento gratuito compatible antes del despliegue público.

Los pagos aparecen como una posibilidad del sistema, no como un servicio adicional ya implementado. Tener seis microservicios supera el mínimo numérico, pero no garantiza la calificación de todos los criterios.

## 17. Fuentes y créditos

### Hoteles de referencia — consulta original del 15 de octubre de 2026

Se escribieron descripciones propias a partir de datos públicos. No se incorporaron logotipos, reseñas, estrellas ni tarifas comerciales de los hoteles. Los precios de ejemplo, capacidades y unidades no son ofertas ni inventario real.

- [GHL Hotel Montería](https://www.ghlhoteles.com/hoteles/colombia/monteria/ghl-monteria/): ubicación junto a Alamedas, Calle 44 No. 8-43 y nombre Business Superior. [Habitaciones](https://www.ghlhoteles.com/en/hotels/colombia/monteria/ghl-monteria/rooms/).
- [Sites Montería](https://www.sitesmonteria.com/es/): Carrera 6 No. 65-24 y Site Loft Business. [Servicios](https://www.sitesmonteria.com/servicios/): Wi-Fi, restaurante Étnico y espacios de trabajo.
- [Hotel Florida Sinú](https://hotelfloridasinu.com/habitaciones): Estándar Doble, Wi-Fi, aire acondicionado y escritorio. [Contacto](https://www.hotelfloridasinu.com/es/contacto): Calle 41 No. 15D-26.

### Fotografías

Son imágenes remotas de Unsplash y **no corresponden a los hoteles nombrados**. No se descargaron fotografías promocionales de sus sitios. Se mantienen créditos en las tarjetas:

- Cory Bjork: [piscina y palmeras](https://unsplash.com/photos/swimming-pool-near-palm-trees-during-daytime-D1yT791Nf9A), imagen de Mission Bay Resort, San Diego. [Archivo remoto](https://images.unsplash.com/photo-1623718649591-311775a30c43).
- visualsofdana: [habitación con cojines azules](https://unsplash.com/photos/white-bed-with-blue-pillows-VoYzj_ITdog), fotografía ilustrativa de Bali. [Archivo remoto](https://images.unsplash.com/photo-1611971263023-105938ce12ed).
- reisetopia: [habitación con ropa de cama floral](https://unsplash.com/photos/white-and-brown-floral-bed-linen-oukA5uMuALg), fotografía ilustrativa de Ámsterdam. [Archivo remoto](https://images.unsplash.com/photo-1592229505678-cf99a9908e03).

Se consultó la [licencia Unsplash](https://unsplash.com/license). La atribución y el aviso de independencia documentan el uso; no se afirma una autorización de los hoteles ni una garantía jurídica general.

### Referencias técnicas utilizadas

- [Python: scrypt](https://docs.python.org/3.12/library/hashlib.html#hashlib.scrypt), [SMTP](https://docs.python.org/3.12/library/smtplib.html), [SQLite](https://docs.python.org/3.12/library/sqlite3.html).
- [Supabase: conexión a PostgreSQL](https://supabase.com/docs/guides/database/connecting-to-postgres).
- [Google: contraseñas de aplicación](https://support.google.com/accounts/answer/185833?hl=es) y [SMTP](https://support.google.com/mail/answer/7104828?hl=es).
- [Vercel: reescrituras](https://vercel.com/docs/rewrites) y [monorepositorios](https://vercel.com/docs/monorepos).
- [Render: límites gratuitos](https://render.com/docs/free), [bloqueo SMTP](https://render.com/changelog/free-web-services-will-no-longer-allow-outbound-traffic-to-smtp-ports), [monorepositorios](https://render.com/docs/monorepo-support) y [Web Services](https://render.com/docs/web-services).
- [OWASP: JWT en APIs](https://cheatsheetseries.owasp.org/cheatsheets/REST_Security_Cheat_Sheet.html#jwt) y [RFC 8725](https://www.rfc-editor.org/rfc/rfc8725.html), consultados al discutir JWT el 22 de octubre.

## 18. Cómo continuar sin perder contexto

Trabajar en esta carpeta de `optativa`. Leer este documento y verificar el estado real de archivos, procesos, Git y proveedores antes de dar por vigentes resultados antiguos. Mantener la independencia de datos, la identidad de Hotels y las aclaraciones sobre las referencias visuales.

Por cada cambio terminado: actualizar este contexto si cambian decisiones o estado, ejecutar las comprobaciones apropiadas, revisar secretos y `git diff --check`, crear un commit descriptivo y verificar la subida cuando se publique. No enviar correos reales solo para comprobar textos. Mantener el despliegue y nuevas migraciones como acciones separadas.

La consolidación documental no elimina requisitos de la guía ni las pruebas ejecutables. Evitar volver a crear informes repetidos de historial, decisiones, fuentes o pruebas cuando la información corresponda a una sección de este archivo.
