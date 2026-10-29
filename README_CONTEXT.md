# Hotels — contexto completo del proyecto

Actualizado el **29 de octubre de 2026**. Este es el documento central de contexto, funcionamiento, herramientas, decisiones, verificación e historial de Hotels. Reúne la información antes distribuida en `HISTORIAL_PROYECTO.md`, `DECISIONES_TECNICAS.md`, `PRUEBAS.md`, `SUPABASE.md` y `FUENTES.md`.

Los resultados de ejecución que se citan conservan sus fechas. Tener código escrito, un proveedor configurado o un commit publicado no significa haber completado un despliegue público ni todos los entregables.

### Recuperación de contraseña y bloqueo por correo — 29 de octubre de 2026

El usuario pidió añadir recuperación y bloquear el acceso después de seis contraseñas incorrectas, mostrando los intentos restantes. Se mantienen seis microservicios: Autenticación es responsable del estado de seguridad y Notificaciones entrega los correos por SMTP. La prioridad acordada es terminar esta funcionalidad antes de discutir el despliegue y organizar la entrega formal.

La versión se desarrolló en `codex/recuperacion-bloqueo-cuentas` y se incorporó a `main` mediante `dd15735`, después de la validación remota. El contador usa el correo normalizado, guardado como SHA-256 en `hotels_auth.login_security`; no depende del navegador ni exclusivamente de la IP. Se permiten seis fallos dentro de una ventana de 15 minutos y el sexto bloquea nuevos accesos por contraseña durante 15 minutos. Los cinco primeros informan los intentos restantes; el sexto devuelve HTTP 429 con `attemptsRemaining=0`, fecha de desbloqueo y `Retry-After`. El acceso correcto reinicia el contador. El bloqueo no se extiende por repetir solicitudes ni impide recuperar la contraseña. Se mantiene el límite adicional de solicitudes por IP.

El estado se serializa por correo mediante UPSERT y bloqueo de fila de PostgreSQL; SQLite utiliza `BEGIN IMMEDIATE`. Así se conserva al reiniciar y varias instancias comparten el mismo límite. Una tarea periódica elimina los contadores y tokens vencidos. Los enlaces de recuperación y contadores temporales no se reproducen al copiar respaldos SQLite, evitando reactivar enlaces consumidos.

`POST /api/auth/forgot-password` responde de forma uniforme para direcciones registradas e inexistentes y limita los reenvíos a uno cada 60 segundos, además de tres solicitudes por minuto por IP. Genera un token aleatorio de 32 bytes, válido 15 minutos, cuyo hash SHA-256 se guarda en `hotels_auth.password_resets`. Un nuevo envío reemplaza el token anterior. El enlace utiliza el origen fijo `PUBLIC_ORIGIN`, con HTTPS fuera de localhost, y lleva el token en el fragmento de `/reset-password.html`, por lo que no forma parte de la ruta registrada por el servidor. La página limpia el fragmento del historial, no carga recursos externos y evita caché y Referer.

`POST /api/auth/reset-password` exige token y contraseña repetida de 10 a 128 caracteres. El consumo del token, la nueva sal/hash scrypt, la revocación de todas las sesiones propias y la eliminación del bloqueo ocurren en la misma transacción. No inicia sesión automáticamente ni modifica permisos administrativos. Dos solicitudes simultáneas con el mismo enlace solo pueden completar un cambio.

Los eventos `password.reset` se entregan por Notificaciones y se excluyen de la bandeja web: una sesión abierta no permite leer el enlace enviado al correo. Auth borra el enlace de su outbox después de entregarlo al servicio; Notificaciones elimina el enlace del cuerpo persistido después de la aceptación SMTP y no envía mensajes de recuperación vencidos. Mientras está en cola, el enlace permanece temporalmente en estos almacenamientos privados para poder entregarse. Un evento `password.changed` avisa después del cambio. No se modificó el esquema de Notificaciones ni se incorporaron sus credenciales en Auth.

La migración `migrations/auth/20261029203309_hotels_account_recovery_lockout.sql`, generada con Supabase CLI, ya se aplicó desde la sesión web autorizada después de la confirmación del usuario. Las dos tablas tienen RLS y políticas exclusivamente para `hotels_auth_app`, sin acceso de `anon`/`authenticated`. Se respaldaron y compararon los dos usuarios originales en `data/backups/account-recovery-20261029T222939Z/auth.json`; sus contraseñas se conservaron. La configuración SMTP privada permanece intacta.

Verificación: 121 comprobaciones HTTP con SQLite, 104 con los seis PostgreSQL, 11 de configuración, nueve de migración, tres de OpenAPI y tres de SMTP simulado aprobadas. Las comprobaciones nuevas cubren el límite exacto, persistencia al reiniciar, aislamiento por correo, recuperación durante el bloqueo, caducidad, doble consumo concurrente, revocación de sesiones y ausencia del enlace en la bandeja web. Las pruebas simuladas verifican TLS, descarte por vencimiento y eliminación del enlace tras el envío. Una primera ejecución PostgreSQL detectó el uso de un `%` literal en la consulta que filtra correos privados; se sustituyó por un parámetro y se corrigió la codificación de los logs de pruebas para no ocultar errores. La ejecución posterior terminó correctamente y la verificación del respaldo confirmó intactos los dos usuarios reales, sin filas de prueba en las dos tablas de seguridad. SMTP permaneció desactivado en las pruebas; no se enviaron correos reales ni se cambió la contraseña de ninguna cuenta del usuario. También se amplió la prueba de Docker con recuperación entre contenedores, privacidad del enlace, revocación y rechazo de reutilización.

La interfaz se revisó en la vista aislada de 8081: mostró los intentos restantes, el bloqueo al sexto fallo y la solicitud de recuperación durante el bloqueo. La pantalla de nueva contraseña elimina el fragmento del enlace de la barra de direcciones. Las capturas están en `rev/work/hotels-bloqueo-sexto-intento.png` y `hotels-recuperacion-formulario.png`; corresponden a una cuenta ficticia de QA. No se usó esa cuenta en las bases reales.

La ejecución de CI [40968372728](https://github.com/DodyCe/hotels/actions/runs/40968372728) aprobó los cuatro trabajos sobre `dd15735`, con 18 comprobaciones de Docker Compose entre siete contenedores, incluidas las cinco nuevas de recuperación y privacidad. Se arrancó la versión final en 8080 y se verificaron los siete health HTTP 200, seis conexiones PostgreSQL y los conteos originales de las bases. Auth conserva dos usuarios, dos perfiles y cero filas de seguridad de prueba; Notificaciones conserva seis mensajes. La vista aislada se detuvo. El formulario final quedó abierto en la página normal y su captura está en `rev/work/hotels-recuperacion-final-8080.png`. El despliegue y el documento formal siguen diferidos por decisión del usuario.

Se consultaron las guías de [recuperación de contraseña](https://cheatsheetseries.owasp.org/cheatsheets/Forgot_Password_Cheat_Sheet.html) y [autenticación](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html) de OWASP para justificar token aleatorio/consumible, vencimiento, mensajes uniformes, revocación y bloqueo temporal.

### Desarrollo del 29 de octubre de 2026 — administración, Docker y OpenAPI

El usuario pidió terminar primero los puntos funcionales: administración, ejecución con Docker y documentación interactiva de APIs; el documento de entrega se organizará después. El trabajo se desarrolló en `codex/administracion-docker-openapi` mientras se preparaban y comprobaban las migraciones de las bases existentes, y se incorporó a `main` tras la validación remota. La aplicación normal se utiliza en el puerto 8080; la vista temporal de 8081 quedó detenida.

Se implementaron roles `guest`/`admin`, perfiles de huéspedes, CRUD administrativo de hoteles y habitaciones, ajustes de inventario que respetan las reservas, retiros lógicos y revocación de sesiones de huéspedes desactivados. El registro público no acepta roles. `tools/set_admin.py` permite promover una cuenta existente por el canal del operador y revoca sus sesiones anteriores. El usuario indicó su cuenta real registrada y confirmó su promoción; ya se ejecutó correctamente, sin publicar el correo ni crear contraseñas predeterminadas.

La nueva administración está en `web/admin.html`. El alta de habitación conserva un estado pendiente si Inventario falla, se reintenta por API y no ofrece la habitación hasta confirmar sus unidades. No hay acceso directo a bases ajenas. Se aplicaron las migraciones de columnas/perfiles de Auth, Catálogo y Habitaciones y dos migraciones posteriores de políticas de edición; se conservan las seis bases existentes.

Se agregaron Swagger UI 5.34.0 y PyYAML 6.0.3. El visor `web/docs.html` sirve el contrato público y uno interno separado; el primero permite probar el Gateway usando la sesión actual y el segundo solo documenta la comunicación privada. Swagger se sirve desde los archivos oficiales locales, con licencia, versión fijada y bundle gzip; no carga una CDN ni requiere Node para ejecutar Hotels. Los secretos internos nunca aparecen en esos contratos.

Verificaciones locales: 96 comprobaciones HTTP con SQLite temporal, 11 de configuración, nueve de migración, dos de OpenAPI, Ruff y ESLint aprobados. Se utilizó una vista de QA aislada en `http://127.0.0.1:8081/`, con datos temporales y SMTP desactivado; se detuvo al iniciar la validación remota final. La nueva suite `tests/compose.py` construye y prueba siete contenedores en un proyecto aleatorio y elimina solo sus volúmenes de prueba. Docker Desktop figura registrado en Windows, pero no se encontraron sus ejecutables; la ejecución real de contenedores se verificó en GitHub Actions.

**Docker verificado:** la ejecución [40930179895](https://github.com/DodyCe/hotels/actions/runs/40930179895), correspondiente al código `ca54b04`, completó correctamente los cuatro trabajos de GitHub Actions. Docker construyó y arrancó siete contenedores sanos y aprobó 13 comprobaciones de registro, sesión, reservas, cancelación, promoción por operador, administración y Swagger. Estas 13 comprobaciones usan seis SQLite aisladas dentro de los contenedores, sin correo ni credenciales reales; no se afirma que prueben las nuevas migraciones en los seis PostgreSQL. Sumadas a las suites HTTP/configuración/migración/OpenAPI, son 131 comprobaciones de esta etapa. El conector GitHub rechazó crear el PR con HTTP 403; la rama sí quedó publicada y se activó CI para pushes de ramas.

**Revisión visual:** se crearon hotel, habitación con inventario y huésped temporales desde el panel; se retiró y reactivó al huésped. Swagger ejecutó `GET /guests` con HTTP 200 usando la sesión administradora de QA y el visor interno no mostró controles de ejecución. No hubo errores/advertencias de consola. El panel se revisó a 390 × 844 y 1366 × 900 sin desbordamiento horizontal; las capturas están en `rev/work/hotels-administracion.png` y `hotels-admin-movil.png`. La cuenta administradora de QA existe solo en esos datos locales desechables.

**Migración de Habitaciones aplicada:** se pudo utilizar su configuración administrativa privada existente. Se respaldaron las seis filas en `data/backups/rooms-admin-20261029T182301Z/rooms.json`, se aplicó `20261029180227_hotels_admin_rooms.sql` y se comprobaron los valores originales conservados, el permiso UPDATE de su rol y RLS habilitado.

**Migración de Auth aplicada:** el usuario abrió su cuenta de Auth/Notificaciones en el navegador y confirmó los permisos de la nueva tabla privada de huéspedes. Se ejecutó `20261029180220_hotels_admin_auth.sql` desde el editor SQL autorizado, conservando los dos usuarios originales y creando sus dos perfiles. Se verificaron RLS y la ausencia de acceso de `anon`/`authenticated`; el respaldo previo está en `data/backups/admin-activation-20261029T192505Z/`. Después se promovió la cuenta real indicada por el usuario mediante el comando de operador y se revocaron sus sesiones anteriores. Notificaciones conserva su base independiente y no necesitó migración en esta etapa.

**Catálogo migrado y RLS corregido:** el usuario abrió la segunda cuenta y se aplicó `20261029180224_hotels_admin_catalog.sql` desde su editor SQL. Se conservaron los tres hoteles y sus documentos. La primera integración aprobó 73 comprobaciones, pero una prueba adicional con los roles reales detectó que conceder UPDATE no bastaba: faltaba la política RLS de UPDATE en Catálogo y Habitaciones, por lo que las ediciones no modificaban filas. Se aplicaron las migraciones posteriores `20261029194429_hotels_catalog_backend_update_policy.sql` y `20261029194451_hotels_rooms_backend_update_policy.sql`, exclusivamente para sus roles de backend y con `USING` y `WITH CHECK`. Seis comprobaciones transaccionales confirmaron inserción, edición, retiro lógico y rollback en Auth/Catálogo/Habitaciones sin dejar datos temporales. Se incorporaron a la suite de integración PostgreSQL como regresión. Las conexiones de aplicación siguen limitadas; no se modificaron credenciales ni se habilitó acceso público a los esquemas. El conector Supabase continuó solicitando reautenticación; las sesiones web autorizadas y la conexión administrativa privada ya disponible para Habitaciones permitieron completar los cambios.

**Integración remota final:** `tests/integration.py --six-postgres` aprobó 79 comprobaciones, incluyendo las seis nuevas de escritura/rollback con los roles reales. SMTP estuvo desactivado y la instancia normal detenida durante la prueba. La limpieza terminó con código 0; se verificaron los dos usuarios originales, sus dos perfiles de huéspedes, tres hoteles y seis habitaciones, y se compararon los datos originales con el respaldo. Después se arrancó la versión integrada desde `optativa/hotels`, conservando el `.env` privado y la configuración de correo. El administrador indicado debe iniciar sesión nuevamente para usar `/admin.html`; Swagger se abre en `/docs.html`. La organización del documento formal y el despliegue público continúan pendientes.

**Arranque normal comprobado:** Gateway y seis servicios devolvieron health HTTP 200; los seis servicios declararon `postgresql`. Las rutas de administración, Swagger y ambos contratos respondieron 200, el bundle gzip local se validó y la consulta de huéspedes sin sesión respondió 401. Se comprobaron los conteos finales de las seis bases: Auth 2 usuarios/2 huéspedes/0 sesiones/2 eventos; Notificaciones 6 mensajes; Catálogo 3 hoteles; Habitaciones 6 tipos; Reservas 2 reservas/4 eventos; Inventario 6 registros/1 asignación. Los datos de las comprobaciones no quedaron en las bases y no se enviaron mensajes reales nuevos.

La integración se publicó en `main` como `258cd62`. Su ejecución de CI [40944082013](https://github.com/DodyCe/hotels/actions/runs/40944082013) aprobó los cuatro trabajos: lint/pre-commit, frontend, suites locales y Docker Compose. Esa ejecución confirma también la versión final de código posterior a la corrección RLS; las 79 comprobaciones remotas se ejecutaron localmente con las conexiones privadas, que no se entregan a GitHub Actions.

### Actualización del 26 de octubre de 2026 — migración de Reservas e Inventario

El usuario confirmó que los dos servicios de esta etapa son **Reservas** y **Disponibilidad e inventario**. Disponibilidad e inventario es un solo dominio y proceso (`services/availability.py`, puerto 8106): conserva las unidades/asignaciones y calcula las unidades libres por fechas. Separarlo en dos dominios sería otro cambio de arquitectura, que no se ha solicitado ni implementado. El total sigue siendo seis microservicios.

En la tercera cuenta se creó la organización gratuita `Hotels` (`utdpmgiymdbumjsnxdyv`) con **dos proyectos**, no tres: `hotels-reservations` (`fhqpyidzbbldxuskckyh`) y `hotels-availability` (`clubrnifkutcjsfvrxlk`). Hotels es el nombre de la organización; no es un proyecto adicional. Las otras cuatro bases permanecen en las cuentas anteriores. Ambos proyectos nuevos se crearon con Data API desactivada, esquemas privados, RLS y roles limitados; las contraseñas y conexiones están fuera de Git.

Se respaldaron las bases y configuración en `data/backups/before-reservations-availability-20261026T152544Z-2629cc/`. La copia a PostgreSQL conservó dos reservas, cuatro eventos de outbox, seis registros de inventario y una asignación/liberación; se comprobó cero pendientes. Los archivos SQLite originales se conservan.

Se implementaron bloqueos PostgreSQL por identificador de reserva/asignación y por habitación para impedir sobreventa entre instancias, cancelaciones idempotentes y recuperación de fallos. La consulta de disponibilidad se adaptó para evitar un viaje SQL por cada noche. Aprobaron 63 comprobaciones SQLite, 11 de configuración y ocho de migración. La primera integración completa con seis PostgreSQL detectó una solicitud concurrente que superaba el tiempo del Gateway: se corrigió reutilizando la conexión durante cada transición y usando aislamiento READ COMMITTED. El registro posterior del 26 contiene 67 comprobaciones aprobadas; la combinación se volvió a verificar el 28, como se detalla a continuación. La publicación estaba pendiente al cerrar la migración; se incorpora junto con el frontend del colaborador en la integración descrita más abajo. Los procesos siguen locales. Las secciones de estado actual ya describen seis PostgreSQL; los resultados históricos conservan sus fechas.

### Revisión del 28 de octubre de 2026 — cambios del colaborador y compatibilidad

El usuario pidió comprobar la página y sus microservicios después de los cambios del colaborador. Se actualizó la referencia remota sin hacer pull sobre el árbol con modificaciones: al comenzar la revisión, la carpeta activa estaba en `59e8102916b416224e1d9a5f486671d245dbcefa` y `origin/main` en `f838cbb124f1558da8f25a8f604f976bbcb2cc7f`. Se usó una copia de revisión separada en `C:\Users\DODY\Documents\Codex\2026-10-15\rev\work\hotels-review-oct28-f838cbb` para conservar los cambios locales. La revisión no creó commits, no hizo push y no mezcló la rama principal de la carpeta activa.

Los pull requests #1 a #9 incorporan CSS/HTML formateado, fuentes y fotografías adaptables, favicon, foco de modales, confirmación antes de cancelar, fechas de Montería, filtro de precio, resumen de cuenta, reservas agrupadas, avisos con presentación de correo, animaciones y barra móvil de reserva. Auth agrega `created` a la respuesta del perfil y Notificaciones importa `hashlib` directamente. También se añadieron OpenAPI, GitHub Actions, ESLint, Ruff y pre-commit. El contrato básico sigue siendo compatible con los seis servicios. Durante esta revisión las mejoras solo estaban en la versión remota y la copia separada; después se incorporaron a la carpeta activa con autorización del usuario.

Resultados de esta revisión:

- **Versión publicada sin nuestras modificaciones pendientes:** 57 comprobaciones de integración con seis SQLite temporales, 57 con sus cuatro PostgreSQL y dos SQLite temporales, nueve pruebas de configuración y cinco de migración, todas aprobadas.
- **Combinación de los cambios remotos con nuestra conexión a las seis bases:** 67 comprobaciones de integración con seis PostgreSQL, 11 pruebas de configuración y ocho de migración, todas aprobadas. Incluye registro, sesiones, acceso por propietario, cálculo de precios, creación/cancelación, notificaciones, recuperación de fallos y concurrencia entre instancias de Reservas e Inventario. Se mantuvo la corrección `raise ... from None` del colaborador en la copia de pruebas.
- **Calidad:** ESLint y sintaxis de ambos JavaScript, Ruff y los seis controles de pre-commit aprobados. Los tres trabajos del último pull request #9 figuran como aprobados en GitHub. El YAML OpenAPI se pudo leer y sus 54 referencias internas se resolvieron; no equivale a una certificación completa del contrato.
- **Navegador contra los seis servicios reales con SQLite temporal:** registro de una cuenta desechable, resumen de cuenta, filtro por precio, reserva desde la barra móvil, consulta agrupada, volver sin cancelar, cancelación confirmada y tres avisos (bienvenida, confirmación y cancelación). No aparecieron errores ni advertencias en la consola. Se revisaron escritorio de 1366 × 900 y móvil de 390 × 844, sin desbordamiento horizontal. Las pruebas automáticas separadas cubrieron los mismos flujos con PostgreSQL.
- **Conservación de datos remotos:** al terminar las pruebas las seis bases conservaron sus conteos iniciales: Auth dos usuarios, cero sesiones y dos eventos; Notificaciones seis mensajes; Catálogo tres hoteles; Habitaciones seis tipos; Reservas dos reservas y cuatro eventos; Inventario seis registros y una asignación/liberación. Ningún outbox quedó pendiente. Las cuentas y reservas de las pruebas se retiraron mediante la limpieza limitada a sus propios identificadores.
- **Correo real:** la configuración privada está completa y Gmail aceptó la autenticación SMTP con TLS y un comando NOOP. Se enviaron cero correos. Esto verifica conexión y autenticación, sin afirmar una entrega nueva en bandeja de entrada. Las pruebas de notificaciones ejecutaron SMTP desactivado.
- **Comprobación final de la combinación:** Gateway y los seis `/health` respondieron HTTP 200; cada microservicio informó `database: postgresql`. Las APIs devolvieron tres hoteles, seis habitaciones y seis registros de inventario/disponibilidad. Se arrancó esta copia en el puerto 8080 con las seis conexiones y SMTP desactivado para la revisión; las bases están en Supabase y los procesos siguen locales.

Las evidencias y registros de esta revisión están en la carpeta temporal de trabajo `rev\work`, fuera del código publicable. La integración posterior conserva los cambios remotos y la migración local ya verificada, como se registra en el siguiente apartado. No falta crear dos bases: **ya existen seis proyectos independientes**. JWT, Docker ejecutado y despliegue público no se dieron por terminados con esta revisión.

### Integración autorizada del 28 de octubre de 2026

El usuario pidió incorporar la combinación ya probada. Se conservaron todos los commits y pull requests del colaborador y se consolidaron encima los cambios de conexión, migración y concurrencia de Reservas e Inventario. El código de la carpeta principal corresponde a esa combinación, sin sustituir las mejoras de frontend, Auth, Notificaciones, OpenAPI o calidad. Las comprobaciones de 67 casos PostgreSQL y 19 pruebas de configuración/migración corresponden exactamente a los archivos de backend integrados; se compararon antes de mover la rama principal. Durante la incorporación también aprobaron 63 comprobaciones de integración SQLite temporal, pre-commit y ESLint. En conjunto, las dos modalidades de integración y las pruebas de configuración/migración suman 149 comprobaciones para esta combinación.

Antes de incorporar se respaldaron las modificaciones, migraciones nuevas, el parche y el `.env` en `data/backups/before-incorporation-20261029T045820Z/`, con manifiesto SHA-256. El `.env` principal se conservó sin cambios; los secretos, los datos y los respaldos quedan fuera de Git. Un stash adicional conserva el árbol anterior. Se usa un avance rápido de Git hacia el commit consolidado para no reescribir ni perder la historia del colaborador. La subida a `origin/main` se verifica comparando el identificador local y remoto.

La instancia de revisión del puerto 8080 se reemplaza por el arranque normal desde `optativa/hotels`, utilizando sus seis PostgreSQL y la configuración SMTP existente. Las pruebas automáticas tienen SMTP desactivado; no se generan correos reales de comprobación. Las bases siguen en Supabase y el frontend, Gateway y microservicios siguen ejecutándose localmente. No se realizó un despliegue público.

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
  migrations/               SQL de los seis microservicios
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
- **Persistencia:** seis proyectos PostgreSQL independientes en Supabase, uno por microservicio. SQLite se conserva como alternativa local explícita y para pruebas temporales; no es la base activa de ninguno de los seis servicios configurados. JSON se usa para las semillas y los mensajes de API.
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
  R --> DR[(PostgreSQL Reservas)]
  C --> DC[(PostgreSQL Catálogo)]
  H --> DH[(PostgreSQL Habitaciones)]
  I --> DI[(PostgreSQL Inventario)]
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

1. **Autenticación — 8101 — `services/auth.py`.** Registra cuentas, valida contraseñas, crea/revoca sesiones, comprueba roles y administra los perfiles de huéspedes, el bloqueo por correo y la recuperación. Usa el proyecto PostgreSQL `hotels-auth`: esquema privado `hotels_auth`, tablas `users`, `guests`, `sessions`, `outbox`, `login_security` y `password_resets`. Un perfil puede existir sin credenciales; su vínculo opcional con una cuenta permanece en esta misma base.
2. **Notificaciones — 8102 — `services/notifications.py`.** Recibe eventos, obtiene el destinatario en Auth, guarda mensajes y gestiona SMTP y reintentos. Usa otro proyecto PostgreSQL, `hotels-notifications`: esquema privado `hotels_notifications`, tabla `messages`.
3. **Reservas — 8103 — `services/reservations.py`.** Guarda propietario, habitación, fechas, huéspedes, importe y estado de la operación, además de su outbox. Usa PostgreSQL en `hotels-reservations`, esquema privado `hotels_reservations`, tablas `reservations` y `outbox`.
4. **Catálogo de hoteles — 8104 — `services/catalog.py`.** Guarda establecimientos, ubicación, descripciones, fuentes y créditos; la tabla `hotels` conserva documentos JSON. Usa PostgreSQL en `hotels-catalog`, esquema `hotels_catalog`, tabla `hotels`. Las habitaciones, tarifas y ocupaciones pertenecen a otros servicios.
5. **Habitaciones — 8105 — `services/rooms.py`.** Tabla `rooms`: identificador, hotel, nombre del tipo, capacidad y precio. Usa PostgreSQL en `hotels-rooms`, esquema `hotels_rooms`, tabla `rooms`.
6. **Disponibilidad e inventario — 8106 — `services/availability.py`.** Tablas `inventory` y `allocations`: unidades por tipo de habitación, ocupación por rango y estado de asignación/liberación. Usa PostgreSQL en `hotels-availability`, esquema privado `hotels_availability`. Disponibilidad e inventario forman un único microservicio.

Cada servicio tiene API, proceso y base propios. Ninguno consulta directamente tablas de otro. Los identificadores entre dominios se resuelven por API; no hay claves foráneas entre proyectos PostgreSQL. Reservas conserva nombres e importe históricos de la operación, aunque los datos de origen cambien.

Hay tres hoteles de referencia y seis tipos de habitación, dos por hotel. Cada tipo comienza con una unidad de inventario de ejemplo. Las semillas `seed/hotels.json`, `seed/rooms.json` y `seed/inventory.json` inicializan solo su servicio; cambiar una semilla no sobrescribe automáticamente registros existentes.

Los archivos anteriores `auth.sqlite3`, `notifications.sqlite3`, `catalog.sqlite3`, `rooms.sqlite3`, `reservations.sqlite3` y `availability.sqlite3` se conservan en `data` junto con los respaldos; no son las bases activas cuando sus URL PostgreSQL están configuradas. Si una URL se deja vacía, ese servicio puede funcionar en SQLite. Una URL configurada e inválida provoca un error, no un cambio silencioso de base.

## 6. Razones de las decisiones

- **Seis dominios:** separar los datos del hotel, características de la habitación, ocupación, transacción, identidad y entrega de mensajes evita mezclar responsabilidades y cumple el mínimo de la guía.
- **Una base por servicio:** cada dominio controla sus tablas y evolución. Las seis bases remotas están en proyectos físicamente separados, no en dos esquemas de una misma base presentada como dos bases independientes.
- **Monorepositorio:** facilita revisar contratos, semillas y pruebas coordinadas. Compartir repositorio o una máquina no obliga a compartir proceso ni base. Un único `start.py` sirve para desarrollo, pero no demuestra despliegues independientes.
- **Gateway:** ofrece una sola entrada para el navegador, enruta las APIs y controla hosts/origen sin entregar la clave interna al frontend. Cada servicio sigue comprobando las autorizaciones de su dominio.
- **Sesiones opacas:** permiten revocación inmediata y un flujo sencillo con cookies. Requieren consultar Auth para validar la sesión; se documentaron como alternativa a JWT.
- **Outbox e idempotencia:** conservar el evento junto con el cambio de negocio permite reintentar sin perderlo cuando Notificaciones no responde. Se utiliza HTTP y trabajadores asíncronos, sin un broker adicional.
- **SMTP configurable:** permite cambiar de proveedor sin modificar la interfaz ni incluir secretos en el código. La cuenta dedicada evita mantener el correo personal como identidad del producto.
- **Dos proyectos Supabase primero:** se eligieron Auth y Notificaciones según la decisión del usuario y el límite gratuito de su cuenta en esa etapa. El 23 de octubre se migraron Catálogo y Habitaciones en una segunda cuenta del usuario. El 26 de octubre se migraron Reservas e Inventario en una tercera cuenta, completando seis bases propias. Las bases están en la nube; los procesos permanecen locales.
- **Presentación profesional:** se retiraron etiquetas repetidas de «práctica» en los flujos principales, manteniendo la independencia de los hoteles y los créditos de las imágenes. Un cambio de textos no convierte los datos de ejemplo en ofertas reales.

## 7. Seguridad implementada y JWT pendiente

Las contraseñas se guardan con **scrypt y sal aleatoria por usuario**, no como texto legible. El código usa `n=32768`, `r=8`, `p=1` y salida de 32 bytes. Las sesiones son tokens aleatorios de ocho horas: solo se guarda su hash SHA-256; cerrar sesión lo revoca. La cookie es `HttpOnly`, `SameSite=Strict` y admite `Secure` con `COOKIE_SECURE=1` para HTTPS.

Los roles `guest`/`admin` se resuelven en Auth en cada operación administrativa. El registro público no permite elegir rol. La promoción de una cuenta registrada se ejecuta por el operador con `python tools/set_admin.py --email <correo>` y revoca sus sesiones anteriores. Desactivar un huésped vinculado impide su inicio de sesión y revoca las sesiones; las cuentas administradoras no se pueden desactivar mediante ese endpoint.

Las APIs comprueban el propietario de reservas y avisos, y Auth limita intentos. Los errores y logs evitan mostrar contraseñas o cookies. El Gateway comprueba host y origen. Las credenciales PostgreSQL solo llegan al servicio dueño y las variables SMTP solo a Notificaciones.

Los proyectos Supabase tienen esquemas privados y tablas con RLS; las políticas de acceso se asignan a su rol técnico. `hotels_auth_app`, `hotels_notifications_app`, `hotels_catalog_app`, `hotels_rooms_app`, `hotels_reservations_app` y `hotels_availability_app` tienen permisos limitados sobre su propio dominio; no pueden crear objetos, administrar roles ni omitir RLS. `hotels_meta.service_owner` impide inicializar un dominio sobre la base del otro. El aprovisionamiento utilizó verificadores SCRAM; las contraseñas quedan en `.env`.

**JWT todavía no está implementado.** El 22 de octubre se recomendó evaluarlo para el futuro despliegue distribuido: Auth firmaría con clave privada y los consumidores validarían con clave pública, comprobando firma, emisor, destinatario y vencimiento. Se necesitarían tokens de acceso cortos, renovación y revocación controladas, además de autorización en cada servicio. Esa conversación no fue una orden de sustituir las sesiones ni una implementación terminada.

La recuperación de contraseña y el bloqueo temporal ya están implementados, como se detalla al comienzo. Siguen pendientes la confirmación de titularidad del correo en el registro, MFA y otros controles de una plataforma pública. El correo de bienvenida no verifica la propiedad de la dirección. HTTPS, cookies seguras y `PUBLIC_ORIGIN` deben configurarse y comprobarse al desplegar. JWT firmado no equivale a cifrar sus datos; nunca debe contener contraseñas.

`.env`, bases, respaldos, `.venv`, claves internas, caches y logs están excluidos de Git. No pegar contraseñas de Gmail o PostgreSQL, tokens ni cookies en este documento, el chat, capturas públicas o commits. No sobrescribir el `.env` actual con la plantilla.

## 8. Reservas, disponibilidad y eventos

Reservas obtiene por API la habitación y su tarifa, valida el hotel y capacidad, guarda la solicitud y pide una asignación a Inventario. El precio lo decide el servidor, no un importe enviado por JavaScript. Inventario verifica las noches en una transacción para evitar doble ocupación. En PostgreSQL usa un bloqueo asesor transaccional por identificador de asignación y un bloqueo de fila por habitación; en SQLite conserva BEGIN IMMEDIATE. Reservas bloquea la transición por identificador y reutiliza su conexión hasta el commit. READ COMMITTED permite ver el estado más reciente después de esperar el bloqueo. La disponibilidad consulta las asignaciones superpuestas una vez y calcula las noches sin una consulta remota por noche. La fecha de salida no ocupa noche; la llegada ese mismo día de otra reserva es válida.

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

El conector MCP seguía autorizado en la primera cuenta; la segunda se administró mediante el panel que abrió el usuario. Se comprobaron sus conexiones de sesión IPv4 en el propio panel, sin añadir IPv4 de pago. Los dos roles de Catálogo y Habitaciones permiten SELECT e INSERT para consulta y migración inicial; no tienen UPDATE, DELETE, creación de objetos/roles ni bypass de RLS. Los esquemas no están expuestos a `anon` o `authenticated`. La Data API quedó desactivada al crear Habitaciones porque el backend usa PostgreSQL directamente.

Supabase había creado `public.rls_auto_enable()` como función administrativa con permisos públicos de ejecución. Se inspeccionó su definición y se revocó EXECUTE a PUBLIC, anon y authenticated, manteniendo el disparador automático de RLS. La corrección queda en los SQL de ambos servicios.

Las migraciones nuevas se generaron con **Supabase CLI 2.121.0**, obtenida del paquete oficial npm mediante `npx`, después de consultar `--help`. Los archivos `migrations/catalog/20261023072457_hotels_catalog_initial.sql` y `migrations/rooms/20261023072500_hotels_rooms_initial.sql` se aplicaron desde el editor SQL del panel, no mediante un `db push` ni un enlace del CLI a la cuenta. No contienen contraseñas; la activación de roles se hizo aparte con verificadores SCRAM. Los archivos privados de aprovisionamiento están bajo `data/provisioning`, fuera de Git y sin entregarse al navegador ni a otros servicios.

Se copiaron los tres hoteles y seis tipos existentes, manteniendo los identificadores, campos, tarifas y orden. PostgreSQL guarda `sort_order` porque no tiene el `rowid` de SQLite. Las APIs conservan el contrato: `hotelId` sigue teniendo esa capitalización y no se expone el campo interno de orden. No se crean claves foráneas entre las bases de Catálogo y Habitaciones.

El **26 de octubre**, en la organización gratuita `Hotels` (`utdpmgiymdbumjsnxdyv`) de la tercera cuenta, se crearon exactamente dos proyectos:

- [hotels-reservations](https://supabase.com/dashboard/project/fhqpyidzbbldxuskckyh), referencia `fhqpyidzbbldxuskckyh`, región `us-east-1`, esquema `hotels_reservations`, rol `hotels_reservations_app`.
- [hotels-availability](https://supabase.com/dashboard/project/clubrnifkutcjsfvrxlk), referencia `clubrnifkutcjsfvrxlk`, región `us-west-2`, esquema `hotels_availability`, rol `hotels_availability_app`. La selección automática de Americas asignó Oregon a este segundo proyecto.

Los dos tienen Data API desactivada, tablas con RLS y roles de aplicación limitados a SELECT/INSERT/UPDATE/DELETE en su propio dominio. Las migraciones `migrations/reservations/20261026152827_hotels_reservations_initial.sql` y `migrations/availability/20261026152830_hotels_availability_initial.sql` se generaron con Supabase CLI 2.121.0 y se aplicaron mediante conexión administrativa psycopg. No se ejecutó `db push` ni se registraron como historial remoto del CLI. Las contraseñas y la activación de login se aprovisionaron aparte. Se conservan dos reservas, cuatro eventos, seis filas de inventario y una asignación/liberación.

Para reproducirlo en proyectos nuevos:

1. En cada proyecto nuevo, aplica como administrador todos los SQL de la carpeta del microservicio en orden de nombre: primero `001_initial.sql` y `002_backend_access.sql` cuando existan, y después las migraciones con fecha. Esto incluye los perfiles/roles, políticas de edición y recuperación/bloqueo añadidos el 29. No vuelvas a ejecutar una migración ya aplicada sobre tablas existentes. Los scripts iniciales crean roles `NOLOGIN`; su activación y contraseña se aprovisionan por un canal privado administrativo. El rol de ejecución no hace DDL.
2. Copia la URI de **Connect → Session pooler**, con el host que muestre el panel, usuario técnico del proyecto y puerto de sesión 5432. No deduzcas el host solo de la región ni uses la URL HTTP, `anon` o una clave publicable como conexión PostgreSQL.
3. Completa `AUTH_DATABASE_URL`, `NOTIFICATIONS_DATABASE_URL`, `CATALOG_DATABASE_URL`, `ROOMS_DATABASE_URL`, `RESERVATIONS_DATABASE_URL` y `AVAILABILITY_DATABASE_URL` con sus conexiones diferentes y `sslmode=require`, codificando caracteres especiales de las contraseñas. Puede utilizarse `verify-full` con el certificado configurado. Son contraseñas de bases, no la contraseña de la cuenta Supabase.

```dotenv
AUTH_DATABASE_URL=postgresql://USUARIO_AUTH.REFERENCIA_AUTH:CONTRASENA_CODIFICADA@HOST_DEL_PANEL:5432/postgres?sslmode=require
NOTIFICATIONS_DATABASE_URL=postgresql://USUARIO_AVISOS.REFERENCIA_AVISOS:OTRA_CONTRASENA_CODIFICADA@HOST_DEL_PANEL:5432/postgres?sslmode=require
CATALOG_DATABASE_URL=postgresql://USUARIO_CATALOGO.REFERENCIA_CATALOGO:OTRA_CONTRASENA_CODIFICADA@HOST_DEL_PANEL:5432/postgres?sslmode=require
ROOMS_DATABASE_URL=postgresql://USUARIO_HABITACIONES.REFERENCIA_HABITACIONES:OTRA_CONTRASENA_CODIFICADA@HOST_DEL_PANEL:5432/postgres?sslmode=require
RESERVATIONS_DATABASE_URL=postgresql://USUARIO_RESERVAS.REFERENCIA_RESERVAS:OTRA_CONTRASENA_CODIFICADA@HOST_DEL_PANEL:5432/postgres?sslmode=require
AVAILABILITY_DATABASE_URL=postgresql://USUARIO_INVENTARIO.REFERENCIA_INVENTARIO:OTRA_CONTRASENA_CODIFICADA@HOST_DEL_PANEL:5432/postgres?sslmode=require
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

Para Reservas e Inventario se usa `--services availability reservations`, primero en modo de comprobación y después con `--apply` solo si se necesita copiar datos de otra instalación no migrada. Las seis bases actuales ya tienen sus datos. La repetición conserva los estados remotos avanzados de reserva, entrega y liberación; no reactiva asignaciones ni revierte cancelaciones.

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

Las rutas de API usan JSON. El Gateway elimina `/api` al reenviar la solicitud:

- `GET /api/hotels` y `GET /api/hotels/{id}`: catálogo.
- `GET /api/rooms?hotelId={id}&guests=2` y `GET /api/rooms/{id}`: tipos, capacidad y tarifa; los filtros son opcionales.
- `GET /api/inventory`: unidades por tipo.
- `GET /api/availability?checkin=AAAA-MM-DD&checkout=AAAA-MM-DD`: disponibilidad por rango.
- `POST /api/auth/register`: `{name,email,password}`; cuenta, sesión y evento de bienvenida.
- `POST /api/auth/login`: `{email,password}`; `GET /api/auth/me`: perfil; `POST /api/auth/logout`: revocación.
- `POST /api/auth/forgot-password`: `{email}`; respuesta uniforme y envío privado de recuperación. `POST /api/auth/reset-password`: `{token,password,confirmPassword}`; cambio, consumo del enlace, desbloqueo y revocación de sesiones.
- `POST /api/reservations`: `{roomId,checkin,checkout,guests}`; `hotelId` opcional debe coincidir con la habitación. Precio y propietario proceden del servidor.
- `GET /api/reservations`: reservas propias; `POST /api/reservations/{id}/cancel`: cancelación propia.
- `GET /api/notifications`: mensajes y estados propios.
- Administración con rol `admin`: `POST /api/hotels`, `PATCH`/`DELETE /api/hotels/{id}`, operaciones equivalentes en `/api/rooms`, `GET`/`POST /api/guests`, `PATCH`/`DELETE /api/guests/{id}` y `PUT /api/inventory/{roomId}`. DELETE realiza un retiro lógico. El parámetro `includeInactive=true` solo se permite a administradores.
- `GET /health` en cada proceso: salud básica; Reservas también informa de su preparación/migración.

`/internal/allocate`, `/internal/release`, `/internal/reconcile`, los eventos y las consultas internas de usuario son comunicación entre servicios, protegida con clave y sin rutas públicas equivalentes en el Gateway.

Estados relevantes: 202 pendiente, 400 datos inválidos, 401 sin sesión, 403 acceso no permitido, 404 recurso inexistente o ajeno, 409 conflicto, 429 exceso de intentos y 503 servicio no disponible. Los ejemplos de identificador incluyen `ghl-monteria-principal` y `ghl-monteria-alternativa`.

El contrato público completo está en [`docs/openapi.yaml`](docs/openapi.yaml) (OpenAPI 3.1), y el privado en `docs/internal-openapi.yaml`. El visor Swagger UI local se abre en `/docs.html`: permite probar la API pública con la sesión vigente y muestra el contrato interno sin habilitar su ejecución. Los scripts se sirven localmente y respetan la CSP. `/auth/me` incluye `created` y `role`; la autorización administrativa se resuelve nuevamente en el servidor en cada operación. El panel `/admin.html` administra hoteles, habitaciones, inventario y huéspedes, con edición y retiro/reactivación.

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

Se corrigió durante el desarrollo un bloqueo de archivos SQLite en Windows cerrando conexiones explícitamente. `node --check` y la revisión de whitespace pasaron en la actualización del 17. La revisión inicial en navegador incluyó cuenta, reserva, notificación, cancelación, cierre de sesión y carga de fotos. El panel administrativo se revisó el 29 en escritorio y móvil con datos de QA, sin desbordamiento; los resultados actuales se detallan al principio. Las capturas conservan su fecha y entorno.

Los resultados del 17 de octubre son históricos. En la consolidación documental del 22 no se repitieron las 123 comprobaciones; la actualización de código del 23 sí volvió a verificar ambas modalidades, como se detalla a continuación. No se han validado carga ni funcionamiento público; los contenedores sí se verificaron el 29 en CI. El SMTP real se comprobó aparte y el usuario confirmó llegada; no se enviaron correos nuevos como parte de esta limpieza ni de las pruebas de administración.

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

### Verificación inicial del colaborador el 28 de octubre

- `tests/integration.py` en modo SQLite temporal, después de cada fusión: 57 de 57 comprobaciones aprobadas. `tests/migration.py`: 5 de 5.
- `tests/database_config.py` no se pudo completar en el equipo de esa sesión porque no tenía `psycopg` instalado. Falla la prueba que exige el driver; no se debe a los cambios.
- El frontend se revisó en navegador con la API simulada, a 390, 1024 y 1440 px. El reformateo de CSS/HTML conservó las 250 reglas CSS y la posición y los estilos calculados de los 260 elementos de la página.
- No se ejecutó la modalidad PostgreSQL ni `INICIAR.cmd` con los seis servicios, porque no había `.env` en ese equipo. Antes de entregar, conviene repetir `tests/integration.py --four-postgres` y revisar el flujo completo con las bases reales.

### Verificación conjunta e integración del 28 de octubre

La revisión posterior sí contó con `.env` y psycopg: pasó la versión publicada con cuatro PostgreSQL (57 comprobaciones) y la combinación con seis PostgreSQL (67), más 11 pruebas de configuración y ocho de migración. Los seis health informaron PostgreSQL, el Gateway respondió HTTP 200 y se conservaron los datos originales después de limpiar solo los registros temporales. Las verificaciones iniciales del colaborador de la subsección anterior son históricas y no representan una limitación actual del equipo principal.

Para exigir los seis PostgreSQL, con la instancia normal detenida:

```powershell
.\.venv\Scripts\python.exe tests/integration.py --six-postgres
```

La prueba se niega a usar bases compartidas mientras Hotels está abierto o existen eventos reales pendientes. Genera identificadores propios y fechas lejanas, desactiva SMTP y retira únicamente sus datos. La comparación previa y posterior confirmó los conteos originales. Las capturas, registros y la comprobación SMTP sin envío están en `rev/work`, fuera del repositorio.

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

Node se usa para herramientas de desarrollo como ESLint y obtención de los archivos fijados de Swagger UI; la web no depende de Node para funcionar. Las versiones están fijadas en `requirements-dev.txt`, `package.json` y `package-lock.json`.

## 14. Docker y alojamiento futuro

Se incluyen siete componentes en Compose: Gateway y seis servicios. Solo el Gateway publica un puerto al anfitrión; las SQLite usan volúmenes separados. Las conexiones PostgreSQL y SMTP se asignan únicamente a sus servicios correspondientes. La imagen ejecuta con un usuario sin privilegios.

Para ejecutar Compose en una instalación con Docker disponible, configura una clave `INTERNAL_API_KEY` de al menos 32 caracteres, conserva las conexiones y ejecuta `docker compose up --build`; abre <http://127.0.0.1:8080/>. `docker compose down` detiene los contenedores; no usar opciones que eliminen volúmenes si se deben conservar los datos. **Docker ya se ejecutó y verificó en GitHub Actions** con siete contenedores y 13 comprobaciones de negocio mediante `tests/compose.py`, usando SQLite temporal y SMTP desactivado. La ejecución de la versión configurada con las seis bases Supabase sigue siendo local mediante Python; no se confunde esa prueba de Compose con un despliegue público o con contenedores conectados a los datos reales.

El presupuesto acordado es gratuito. Los seis servicios ya tienen sus bases remotas independientes en Supabase. El destino será **frontend + Gateway + seis microservicios + seis bases independientes en la nube**. Subir únicamente las bases no aloja la aplicación completa.

Vercel se consideró para el frontend, con reescritura externa de `/api` hacia el Gateway para conservar el flujo del navegador; requerirá comprobar origen, hosts, HTTPS y cookies. Publicar HTML solo no habilita reservas.

En la evaluación del **17 de octubre**, Render gratuito no era compatible con el diseño actual: bloqueo de SMTP saliente por 25/465/587, archivos efímeros y ausencia de discos persistentes para las SQLite. También se registraron suspensión por inactividad y una cuota de horas compartida por el espacio de trabajo. Las condiciones del proveedor deben volver a comprobarse antes de elegir alojamiento; esa investigación no fue un despliegue ni una contratación. Un monorepositorio puede alimentar despliegues por servicio, pero ejecutar todo con `start.py` en una sola instancia no prueba independencia de despliegue.

**GitHub está autorizado para avances terminados y revisados; el despliegue público sigue pendiente.** No contratar planes ni crear recursos de pago. El proveedor definitivo de alojamiento del frontend, Gateway y microservicios aún no está elegido; las seis bases ya están en Supabase.

## 15. Historial de avances

- **15 de octubre:** revisión del caso 6 y diseño inicial HTML/CSS/JS; evolución a Hotels, búsqueda de referencias de Montería y fotografías ilustrativas. Incorporación de cuentas, reservas y notificaciones, seguida de separación de Catálogo, Habitaciones e Inventario hasta completar seis dominios.
- **17 de octubre:** aprovisionamiento de dos PostgreSQL independientes en Supabase, roles privados, respaldo/migración, corrección de precisión de fechas, verificación de integración y Gmail dedicado con recepción confirmada por el usuario. Mejora de textos de producto y documentación de límites.
- Hubo una pausa de subidas para terminar desarrollo local; después se autorizó versionar avances en GitHub para conservar un historial. Esa autorización no incluía despliegue ni migración de las otras cuatro bases.
- **22 de octubre:** se restableció el servidor local detenido; se aclaró la ubicación de los archivos, diferencia entre bases locales/remotas, sesiones/JWT y función del Gateway. El usuario trasladó Hotels a `optativa` y solicitó consolidar documentación y retirar copias sobrantes.
- La documentación quedó centralizada en este archivo, con `README.md` como entrada breve. La orden de borrado fue bloqueada por la revisión automática de ejecución; se utilizó la alternativa autorizada de separar los sobrantes. Se movieron cinco documentos sustituidos y quince archivos de entregas anteriores (tres ZIP, cinco capturas y siete archivos del boceto) a `C:\Users\DODY\Documents\Codex\2026-10-15\rev\PARA_ELIMINAR_HOTELS_20261022`. La carpeta `outputs` antigua quedó vacía. No se borraron definitivamente esos archivos ni se trasladaron código activo, pruebas ejecutables, bases, respaldos o credenciales.

- **23 de octubre:** Catálogo y Habitaciones pasaron a dos PostgreSQL propios de la segunda cuenta. Se generaron migraciones, roles limitados, respaldos y conexiones privadas, se conservaron los datos y el contrato de API y se aprobaron 128 comprobaciones. Continúan seis microservicios, con cuatro bases remotas y dos locales; no se desplegaron los procesos en la nube.
- **26 de octubre:** migración de Reservas e Inventario a dos proyectos independientes de la tercera cuenta, conservando datos y completando seis bases Supabase.
- **28 de octubre:** se auditó el código y se integraron mejoras de frontend y documentación mediante los pull requests #1 a #9. Ningún cambio modifica el esquema de las bases ni rompe el contrato existente:
  - **Mantenimiento:** CSS e `index.html` formateados (antes estaban en líneas únicas) y Google Fonts cargado con `<link>` y `preconnect`.
  - **Experiencia de uso:**
    - Imagen principal con `srcset` y confirmación antes de cancelar una reserva.
    - Foco gestionado en los modales y estado de carga de la disponibilidad.
    - Avisos por tipo que se ven sobre el modal.
    - Destino como texto fijo, entrada animada del hero (respeta el movimiento reducido) y favicon en SVG y PNG.
    - Filtro de precio, resumen en «Mi cuenta», reservas agrupadas por estado y notificaciones con formato de correo.
    - Animaciones breves: entrada y salida del modal y de los avisos, resumen resaltado y total animado al elegir habitación, tarjetas que se elevan y aparecen al hacer scroll, y reacomodo con View Transitions al filtrar u ordenar. Todo se desactiva con «reducir movimiento» y no usa estilos en línea, para respetar la CSP.
    - Brillo de carga sobre las tarjetas mientras se consulta la disponibilidad, y barra fija en móvil (hasta 800 px) con el hotel elegido, el total y «Reservar». La barra se oculta cuando el panel «Tu estancia» está a la vista.
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

1. Preparar la evidencia final del frontend: las pruebas de interfaz con servicios reales, la conexión a los seis PostgreSQL y los flujos de integración ya se verificaron el 28 de octubre; falta organizar el material de la demostración formal.
2. Organizar la evidencia del panel administrativo ya implementado: altas, consultas, ediciones, retiros lógicos y reactivación de hoteles, habitaciones y huéspedes, además del ajuste de inventario.
3. Elaborar los modelos de datos formales por servicio. La especificación OpenAPI ya está en `docs/openapi.yaml`.
4. Preparar los dos diagramas solicitados y el documento final con decisiones, seguridad y comunicación asíncrona justificadas.
5. Incorporar la ejecución Docker Compose ya aprobada en CI a las evidencias y al manual de instalación.
6. Capturar evidencias actuales y correo recibido, completar manual, presentación y demostración integral.
7. La recuperación ya está implementada. La confirmación de correo en el registro y una posible migración a JWT quedan como evolución posterior, no como funciones ya terminadas.
8. Seleccionar alojamiento gratuito compatible y verificar el despliegue público del frontend, Gateway y microservicios. La migración de las seis bases a Supabase ya está completada.

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
