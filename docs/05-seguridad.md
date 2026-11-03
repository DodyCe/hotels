# 5. Seguridad

## 5.1 Autenticación

**Contraseñas:** se guardan con scrypt (`n=32768`, `r=8`, `p=1`, 32 bytes) y sal aleatoria por usuario. Nunca se guardan ni se registran en texto.

**Sesión:** al iniciar sesión, Auth genera un token aleatorio y guarda solo su hash SHA-256. El navegador recibe el token en la cookie `hotels_session`:

- `HttpOnly`: JavaScript no puede leerla.
- `SameSite=Strict`: el navegador no la envía desde otros sitios.
- `Max-Age` de ocho horas.
- `Secure` cuando `COOKIE_SECURE=1` (HTTPS).

Cerrar sesión borra la sesión en la base. Cambiar la contraseña o desactivar a un huésped revoca todas sus sesiones.

La justificación frente a JWT está en la decisión D5 de [04-decisiones-tecnicas.md](04-decisiones-tecnicas.md).

## 5.2 Bloqueo por intentos fallidos

- Se cuentan los fallos por correo (guardado como SHA-256 del correo normalizado), no por navegador.
- Con seis fallos dentro de 15 minutos, la cuenta queda bloqueada 15 minutos para el acceso con contraseña.
- Los primeros cinco fallos devuelven 401 con `attemptsRemaining`. El sexto devuelve 429, `attemptsRemaining = 0` y `Retry-After`.
- Un acceso correcto reinicia el contador. El bloqueo no impide pedir la recuperación.

Además hay límites por IP: 12 intentos de acceso por minuto, 3 solicitudes de recuperación por minuto y 12 cambios de contraseña por minuto.

## 5.3 Recuperación de contraseña

1. `POST /api/auth/forgot-password` responde siempre 202, exista o no el correo. Así no se puede averiguar qué correos están registrados.
2. Si existe, Auth genera un token aleatorio de 32 bytes, guarda su hash y publica el evento `password.reset`. Se permite un reenvío cada 60 segundos.
3. Notificaciones envía el enlace `/reset-password.html#token=...`. El token va en el fragmento (`#`), que el navegador no manda al servidor ni queda en los logs.
4. El enlace vale 15 minutos y un solo uso. Al usarlo se cambia la contraseña, se desbloquea la cuenta y se cierran todas las sesiones.

## 5.4 Autorización

- **Huésped:** solo ve y cancela sus reservas y sus avisos. Pedir la reserva de otro usuario devuelve 404, no 403, para no confirmar que existe.
- **Administrador:** puede crear, editar, retirar y reactivar hoteles, habitaciones y huéspedes, y ajustar inventario.
- Cada servicio vuelve a preguntar a Auth el rol en cada operación administrativa (`common.admin_for`). No se confía en datos del navegador.
- El registro público siempre crea `guest` y rechaza con 400 un campo `role`. La promoción a `admin` la hace un operador con `tools/set_admin.py`.

## 5.5 Comunicación entre servicios

- Las llamadas internas llevan `X-Internal-Key`. Sin ella, las rutas `/internal/*` responden 403.
- La clave tiene al menos 32 caracteres; si no, el servicio no arranca.
- El Gateway nunca expone rutas `/internal/*` al navegador.
- Notificaciones obtiene el correo del destinatario en Auth; no acepta direcciones enviadas por el navegador.

## 5.6 Gateway y navegador

- Valida `Host` en todas las peticiones, y `Origin` y `Sec-Fetch-Site` en las que cambian datos.
- Exige `Content-Type: application/json` en POST, PATCH y PUT (415 si no).
- Cabeceras: `Content-Security-Policy` sin scripts externos, `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff` y `Referrer-Policy`.
- Cuerpo máximo de 16 KB (413 si se supera).
- Detrás de Vercel exige `X-Origin-Secret`, para que nadie llame directamente al Gateway publicado en Render.

## 5.7 Bases de datos

- Cada servicio solo tiene la cadena de conexión de su base.
- Esquemas privados con RLS. Las tablas no están expuestas a los roles públicos de Supabase (`anon`, `authenticated`).
- Rol técnico por servicio (`hotels_auth_app`, `hotels_rooms_app`, ...) sin permisos para crear objetos, administrar roles ni saltarse RLS.
- Todas las consultas usan parámetros, no concatenación de texto.

## 5.8 Secretos

- Claves de PostgreSQL, Gmail y la clave interna están en `.env`, que está en `.gitignore`.
- `.env.example` solo trae nombres de variables, sin valores.
- Los logs no muestran contraseñas, cookies ni tokens.
- pre-commit revisa en cada commit que no se suban claves privadas.

## 5.9 Pendiente

- Confirmar la titularidad del correo al registrarse (el correo de bienvenida no lo verifica).
- Autenticación en dos pasos.
- JWT si se separan los servicios en redes distintas.
- Publicar la app OAuth de Google para que el permiso de Gmail no venza cada siete días.
