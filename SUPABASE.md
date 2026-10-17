# Dos bases independientes en Supabase

Se crearon el 17 de octubre de 2026 en la organización **dody's projects**, plan gratuito, región `us-east-1`. La cotización del conector fue USD 0 mensuales por proyecto. No se activaron complementos de pago.

- **Autenticación:** [hotels-auth](https://supabase.com/dashboard/project/abszvtlzemhccsiiwgqx). Referencia `abszvtlzemhccsiiwgqx`. Esquema privado `hotels_auth`: `users`, `sessions`, `outbox`.
- **Notificaciones:** [hotels-notifications](https://supabase.com/dashboard/project/lhygyaadbiflclxeebxu). Referencia `lhygyaadbiflclxeebxu`. Esquema privado `hotels_notifications`: `messages`.

Son dos proyectos PostgreSQL físicos diferentes. No se simula la separación creando dos esquemas en una sola base. Cada base contiene además `hotels_meta.service_owner`, que impide inicializar el servicio equivocado en ella.

Reservas, Catálogo de hoteles, Habitaciones y Disponibilidad e inventario mantienen sus cuatro bases SQLite individuales. Siguen existiendo seis microservicios de negocio y un Gateway.

## Estado actual

Las migraciones están aplicadas y ambas conexiones privadas están configuradas en el `.env` local. Se crearon los usuarios técnicos `hotels_auth_app` y `hotels_notifications_app`, con contraseñas aleatorias independientes. Cada uno tiene acceso a los datos de su servicio y lectura de la marca de pertenencia; no puede crear tablas, administrar roles ni omitir RLS.

Se respaldaron las bases originales y se migraron la cuenta, la sesión existente, el evento de bienvenida y tres notificaciones. Las sesiones caducadas se eliminan normalmente al iniciar sesión; el migrador actualizado copia solo las que siguen vigentes. Se comprobó el arranque real y **57 verificaciones HTTP con Supabase**, además de las 57 del modo SQLite y nueve pruebas de configuración/migración. Los procesos normales ya responden `database: postgresql` en sus endpoints de salud.

Las contraseñas generadas permanecen únicamente en el `.env` privado del equipo. El aprovisionamiento remoto utilizó verificadores SCRAM, sin guardar contraseñas en texto claro en archivos SQL ni en GitHub. No se cambió la contraseña de la cuenta Supabase ni la del administrador PostgreSQL.

## Configurar otra instalación

En este equipo ya está configurado: basta ejecutar `INICIAR.cmd`. Las siguientes indicaciones son para una instalación nueva; conserva las conexiones existentes al actualizar.

1. En cada proyecto abre **Connect → Direct → Session pooler → URI**. El pooler de sesión usa IPv4 y el puerto 5432, sin necesitar el complemento IPv4 de pago. Consulta la [guía oficial](https://supabase.com/docs/guides/database/connecting-to-postgres).
2. En un proyecto nuevo aplica `001_initial.sql` y `002_backend_access.sql` de su carpeta de migraciones como administrador. El segundo archivo crea el usuario técnico sin acceso de inicio de sesión; debe activarse y recibir una contraseña privada por un canal administrativo. No incluyas esa contraseña en los archivos SQL compartidos.
3. Usa el usuario técnico y la contraseña de **cada proyecto**, distintos de los de tu cuenta Supabase. La URI del pooler debe usar `hotels_auth_app.REFERENCIA` o `hotels_notifications_app.REFERENCIA`. Copia cada URI a su variable en `.env` y agrega `?sslmode=require`. Codifica los caracteres especiales de la contraseña para una URL. Se puede usar `sslmode=verify-full` con el certificado raíz configurado.

```dotenv
AUTH_DATABASE_URL=postgresql://hotels_auth_app.abszvtlzemhccsiiwgqx:CONTRASENA_CODIFICADA@aws-0-us-east-1.pooler.supabase.com:5432/postgres?sslmode=require
NOTIFICATIONS_DATABASE_URL=postgresql://hotels_notifications_app.lhygyaadbiflclxeebxu:OTRA_CONTRASENA_CODIFICADA@aws-0-us-east-1.pooler.supabase.com:5432/postgres?sslmode=require
```

El host del pooler fue comprobado en el panel de ambos proyectos; para proyectos nuevos cópialo del panel, pues no se puede deducir únicamente de la región. No uses la URL HTTP del proyecto, la clave publicable ni la clave `anon` como conexión PostgreSQL. No pegues las contraseñas en el chat ni las subas a GitHub.

4. Instala el driver en un entorno local, desde la carpeta del proyecto:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

En el equipo de elaboración ese entorno y el driver ya se prepararon. `INICIAR.cmd` lo utiliza si existe.

## Conservar las cuentas y los avisos anteriores

Detén Hotels con Ctrl+C antes de copiar. Tras completar `.env`:

```powershell
.\.venv\Scripts\python.exe tools/migrate_supabase.py
.\.venv\Scripts\python.exe tools/migrate_supabase.py --apply
.\.venv\Scripts\python.exe tools/migrate_supabase.py
```

El primer comando comprueba ambas bases y cuenta filas pendientes, sin copiar ni mostrar correos, hashes o contraseñas. `--apply` respalda las bases SQLite existentes en `data/backups/supabase-.../`, valida las tablas creadas mediante las migraciones y copia usuarios, sesiones vigentes, outbox y mensajes. Conserva identificadores, sales y hashes scrypt: las reservas locales siguen vinculadas a las mismas cuentas.

No elimina SQLite ni sobrescribe filas remotas. Los reintentos conservan el estado de entrega que ya avanzó en PostgreSQL; un conflicto en los datos originales interrumpe la copia. Cada proyecto se escribe en su propia transacción: no hay una transacción distribuida entre ambos. Si el segundo falla, se puede corregir y repetir la migración sin duplicar lo que terminó en el primero.

En la última comprobación, `pendientes` debe ser cero para cada tabla. Después inicia `INICIAR.cmd`. `GET http://127.0.0.1:8101/health` y `GET http://127.0.0.1:8102/health` deben responder `database: postgresql`. Una URL configurada pero inválida provoca error; no se cambia silenciosamente a SQLite.

## Límites de acceso y del flujo de correo

Los esquemas de aplicación son privados y sus tablas tienen RLS activado con políticas exclusivas del usuario técnico correspondiente. `anon` y `authenticated` no tienen acceso a esos esquemas. El backend dispone de permisos de consulta y modificación sobre sus propias tablas; el navegador no tiene acceso directo. Las migraciones administrativas se aplican por separado, porque los usuarios de ejecución no pueden modificar los esquemas.

`start.py` entrega a Autenticación únicamente `AUTH_DATABASE_URL`; Notificaciones recibe únicamente `NOTIFICATIONS_DATABASE_URL` y las variables SMTP. Los demás procesos no reciben esas credenciales. Compose también configura cada URL solo en su servicio.

Esta fase conserva el servicio de autenticación propio con scrypt y sesiones opacas; **no utiliza el producto Supabase Auth**. Notificaciones continúa consultando el correo por la API interna de Autenticación. No hay claves foráneas ni consultas cruzadas entre las dos bases.

Supabase almacena los datos; el correo sigue saliendo mediante el SMTP Gmail configurable. Conectar estas bases no configura Gmail ni prueba la entrega a una bandeja de entrada. Las vistas previas antiguas no se convierten automáticamente en envíos reales.

## Pruebas disponibles

```powershell
.\.venv\Scripts\python.exe tests/integration.py
.\.venv\Scripts\python.exe tests/database_config.py
.\.venv\Scripts\python.exe tests/migration.py
.\.venv\Scripts\python.exe tests/integration.py --postgres
```

La primera suite ejecuta 57 comprobaciones de los seis servicios con SQLite temporal y desactiva las URL PostgreSQL, incluso si el entorno tiene otras configuradas. La segunda ejecuta seis pruebas de separación entre proyectos, TLS, errores sin secretos y distribución de credenciales. La tercera ejecuta tres pruebas de respaldo, sesiones caducadas, reintentos y conflictos sin sobrescritura.

`--postgres` ejecuta las 57 comprobaciones HTTP con las dos bases reales de `.env` y los otros cuatro servicios en SQLite temporal. Usa cuentas únicas de `example.test` y SMTP desactivado; al terminar elimina solo las cuentas y mensajes de esa ejecución. La reserva local del usuario no se utiliza ni se modifica. La limpieza de sesiones caducadas de Auth funciona igual que en el arranque normal.

Los archivos de `migrations/auth/` y `migrations/notifications/` permiten reproducir los esquemas, usuarios técnicos y permisos en sus respectivos proyectos. No contienen contraseñas ni datos de usuarios.
