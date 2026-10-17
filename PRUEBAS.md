# Verificación de Hotels

## Verificación previa a la actualización de GitHub: 17 de octubre de 2026

- Se repitieron las 57 comprobaciones de integración con SQLite temporal y las 57 con las dos bases PostgreSQL de Supabase y cuatro SQLite temporales: ambas ejecuciones aprobaron con salida 0. SMTP estuvo desactivado y las cuentas y mensajes creados por la ejecución remota se limpiaron al terminar.
- Se repitieron las seis pruebas de configuración y las tres de migración: todas aprobaron. Total de esta verificación: **123 comprobaciones aprobadas**.
- `node --check web/app.js` y `git diff --check` no detectaron errores. Se revisaron los archivos publicables y el historial existente para detectar coincidencias de los secretos configurados y patrones de claves; no hubo coincidencias. `.env`, datos de usuarios, respaldos y `.venv` permanecen excluidos.
- La autorización de esta actualización es guardar código y documentación en GitHub. No se desplegó la aplicación, no se migraron las cuatro bases SQLite restantes y no se enviaron correos reales adicionales. La ejecución con Docker y la revisión visual completa siguen pendientes.

## Revisión de textos y documentación: 17 de octubre de 2026

Se revisaron los textos de la web y las plantillas de bienvenida, confirmación y cancelación para usar lenguaje profesional, manteniendo la aclaración de independencia y las fotografías ilustrativas. No se reescribieron mensajes históricos ni se enviaron correos adicionales por este cambio.

Se repitieron las 57 comprobaciones de integración con SQLite temporal y SMTP desactivado, las seis pruebas de configuración de bases y las tres de migración: todas aprobaron. `node --check web/app.js` no detectó errores de sintaxis. El Gateway respondió HTTP 200 y sirvió el texto actualizado. Los seis endpoints de salud respondieron correctamente; Auth y Notificaciones indicaron PostgreSQL. Esta revisión no sustituye las pruebas visuales de escritorio y móvil pendientes ni una nueva ejecución con Docker. No se publicaron cambios.

## Actualización Supabase: 17 de octubre de 2026

- Se crearon `hotels-auth` y `hotels-notifications` como dos proyectos independientes, gratuitos, en `us-east-1`. Se aplicaron sus migraciones iniciales y se comprobaron las tablas, las claves y RLS mediante el conector Supabase.
- En la base real de Auth se verificaron, dentro de una transacción revertida, inserción de usuario/sesión/evento, consulta de sesión, rechazo de correo duplicado, programación y confirmación de outbox y revocación de sesión.
- En la base real de Notificaciones se verificaron, dentro de una transacción revertida, recepción idempotente de eventos y persistencia del contador y fecha de reintento. También se comprobó que cada base no contiene el esquema del otro dominio. No quedaron filas de estas pruebas.
- `tests/integration.py`: **57 comprobaciones aprobadas** con SQLite temporal; `tests/integration.py --postgres`: **otras 57 aprobadas** usando las dos bases Supabase y cuatro SQLite temporales. SMTP desactivado en ambas ejecuciones. Se limpiaron las cuentas y avisos ficticios de la prueba remota.
- `tests/database_config.py`: **6 pruebas aprobadas** de proyectos distintos, rechazo de una misma base por conexión directa/pooler, configuración incompleta, errores sin contraseña, TLS y credenciales por proceso.
- `tests/migration.py`: **3 pruebas aprobadas** de respaldo completo, copia de sesiones vigentes, repetición sin revertir entregas y conflicto con rollback sin sobrescritura.
- Se instaló `psycopg[binary] 3.3.6` en `.venv`, excluido de Git. Las conexiones y las bases locales también permanecen excluidas.
- Se generó un usuario técnico por proyecto, con contraseñas aleatorias en `.env` y verificadores SCRAM en Supabase. Se comprobó desde esas conexiones que no pueden crear objetos de base, crear tablas ni omitir RLS.
- Se respaldaron las SQLite originales en `data/backups/supabase-20261017T173344Z-03aa7c6f/` y se migraron la cuenta, la sesión existente, un evento y tres mensajes. Tras las pruebas permanecen la cuenta y los tres avisos originales; las sesiones caducadas se depuran normalmente al iniciar sesión.
- Se inició la aplicación normal en 8080. Los endpoints de salud 8101 y 8102 respondieron `status: ok` y `database: postgresql`.
- La verificación posterior de la migración devuelve cero pendientes y conserva exactamente los campos originales. Se utiliza lectura binaria PostgreSQL para evitar falsos conflictos por el redondeo textual de fechas Unix cuando `extra_float_digits=0`. Después del ajuste se repitieron satisfactoriamente las 57 comprobaciones remotas y se reiniciaron los procesos normales.
- El asesor de seguridad de Supabase no devolvió observaciones en ninguno de los dos proyectos después de configurar los roles y políticas.
- Gmail se configuró posteriormente el mismo día: `tools/test_smtp.py --send` terminó con salida 0 y aceptación del proveedor SMTP. Después se sustituyó el remitente personal por una cuenta dedicada a Hotels y se repitió la prueba con aceptación de Gmail. Cada ejecución envió un único mensaje a una cuenta del proyecto. Se reiniciaron los seis servicios para cargar el remitente nuevo. El usuario confirmó después la recepción de las notificaciones en Gmail. No se ha incorporado una captura de esa recepción a este informe. Las credenciales permanecen en `.env`, excluido de Git.
- **Pendiente externo:** recopilar la captura de recepción para la entrega y ejecutar Docker.

Fecha: 15 de octubre de 2026. Ejecución local en Windows con Python 3.12.14. Resultado final del script incluido: **57 comprobaciones aprobadas y salida 0**.

Tras separar los seis microservicios se ejecutó nuevamente el verificador. Se utilizaron cuentas ficticias con dominio `example.test`, bases temporales y SMTP desactivado. No se enviaron correos reales ni se hicieron reservas en los hoteles.

## API e integración

1. Registro de cuenta con sesión.
2. Cookie HttpOnly y SameSite.
3. Perfil autenticado y correo persistido.
4. Segunda cuenta independiente.
5. Rechazo de consultas sin sesión.
6. Contraseña incorrecta rechazada.
7. Inicio de sesión con contraseña correcta.
8. Correo duplicado rechazado.
9. Origen externo rechazado.
10. Eventos internos no expuestos en Gateway.
11. Dos solicitudes concurrentes al mismo cupo: una devuelve 201 y otra 409.
12. Precio calculado por el servidor; se ignora el total enviado por el cliente.
13. Aislamiento de reservas entre usuarios.
14. Otra cuenta no puede cancelar la reserva.
15. Inventario bloqueado después de reservar.
16. Cancelación por el propietario.
17. Cancelación idempotente.
18. Inventario liberado tras cancelar.
19. Fechas inválidas rechazadas.
20. Bienvenida, confirmación y cancelación llegan a Notificaciones.
21. Destinatario obtenido en Auth; se ignora un correo ajeno enviado por el cliente.
22. Repetir una cancelación no duplica el aviso.
23. Sin configuración SMTP se registra vista previa, sin envío real.
24. Aviso académico en todos los correos.
25. Contraseña persistida con sal y derivación scrypt.
26. Cerrar sesión revoca el acceso.

Durante la preparación del verificador se corrigió un bloqueo de archivos en Windows cerrando explícitamente las conexiones SQLite. La versión final pasó la ejecución completa y la limpieza de sus bases temporales.


## Separación de dominios y recuperación de fallos

La versión ampliada añadió comprobaciones que elevan el total de 26 a 57:

- Catálogo de hoteles separado de precios, tipos y ocupación.
- Seis tipos de habitación, filtrado por hotel y capacidad, validación y respuestas 404.
- Un registro de inventario por tipo y un proceso de salud por servicio.
- Existencia de seis bases independientes.
- Migración de una reserva confirmada y otra cancelada con el esquema anterior; conservación de importes y bloqueo de los cupos correspondientes.
- Repetición idempotente de la migración.
- Rechazo de habitaciones de otro hotel, exceso de huéspedes y fechas fuera del formato canónico.
- Reserva de dos tipos distintos del mismo hotel sin mezclar sus cupos.
- Precio obtenido en Habitaciones, asignaciones idempotentes y rechazo de asignaciones tardías después de liberar.
- Caída de Inventario al reservar: respuesta 202 y estado Pendiente; recuperación y confirmación al reiniciar.
- Caída de Inventario al cancelar: estado Cancelando; recuperación y liberación al reiniciar.
- Persistencia de los estados al reiniciar Reservas.

Las pruebas usan los puertos 18080 y 18101–18106 y datos temporales. No detienen ni alteran los servicios normales del usuario. Se verificó además que, tras migrar la aplicación local, se mantienen la cuenta y la reserva cancelada existentes.

## Navegador

Se comprobó el registro de una cuenta, la reserva desde la interfaz, la aparición de su correo de confirmación en Notificaciones, la cancelación y el cierre de sesión. Las tres fotografías cargaron desde internet. Se revisaron escritorio y un ancho de celular de 390 px; el documento no mostró desbordamiento horizontal.

## Pendiente de verificación externa

En la verificación inicial del 15 de octubre no se probó SMTP externo; la actualización del 17 de octubre, descrita arriba, sí comprobó la aceptación de un correo real por Gmail. Docker no estaba disponible; no se ejecutaron los contenedores. No se hizo una prueba de carga ni una validación para despliegue público.
