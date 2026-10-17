# Verificación de Hotels

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

No se probó entrega SMTP a un proveedor externo porque no se configuraron credenciales. Docker no estaba disponible; no se ejecutaron los contenedores. No se hizo una prueba de carga ni una validación para despliegue público.
