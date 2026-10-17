# Historial de Hotels

Registro para preparar el documento técnico y la sustentación del proyecto 6: Sistema de Reservas Hoteleras. Actualizado el 17 de octubre de 2026. Distingue lo implementado de las propuestas y de las verificaciones pendientes.

## Instrucciones vigentes

- **Versionar en GitHub los avances terminados y comprobados.** El 17 de octubre el usuario autorizó subir el código de las dos conexiones Supabase y los demás avances para conservar el historial exigido por la guía. Esta autorización reemplaza la pausa anterior de subidas. El despliegue público continúa pendiente hasta completar el frontend y los microservicios con sus bases.
- El presupuesto de alojamiento es gratuito. No contratar planes, crear recursos de pago ni asumir costos.
- Usar el nombre Hotels y presentar una aplicación realista, con textos profesionales. Evitar repetir «práctica» en la interfaz y en los asuntos de correo.
- Los hoteles reales son referencias. Mantener una aclaración accesible sobre la independencia del proyecto, los datos de ejemplo y la ausencia de reservas reales en los establecimientos. Conservar créditos y aclaraciones de las fotografías ilustrativas.
- Registrar la razón de cada decisión técnica para el documento final. No presentar funcionalidades propuestas, pruebas pendientes o despliegues futuros como terminados.

## Evolución registrada

### Diseño y separación de dominios

1. Se revisó la guía original `PROYECTO FINAL_mivcroservicios GRUPO 11-2.docx` y se eligió el proyecto 6. La guía exige al menos cinco microservicios.
2. Se creó el boceto con HTML, CSS y JavaScript y se renombró a Hotels. Se incorporaron referencias a GHL Hotel Montería, Sites Montería y Hotel Florida Sinú, enlaces a sus sitios y fotografías de Unsplash identificadas como ilustrativas.
3. Se agregó Autenticación y se vinculó con Notificaciones: los avisos obtienen el destinatario desde la cuenta del usuario. Se eligió SMTP configurable.
4. Se separaron Catálogo de hoteles, Habitaciones y Disponibilidad e inventario. El resultado es seis microservicios de negocio, además del API Gateway.
5. Se creó previamente el repositorio público `https://github.com/DodyCe/hotels`. El repositorio remoto existente no significa que las modificaciones locales posteriores ya estén publicadas.

### Persistencia y funcionamiento local

- Cada servicio tiene su propia base y accede a los otros dominios mediante APIs. No se consultan tablas ajenas.
- Por elección del usuario se conectaron primero Autenticación y Notificaciones a dos proyectos Supabase separados: `hotels-auth` y `hotels-notifications`, en la organización `dody's projects`.
- Reservas, Catálogo, Habitaciones y Disponibilidad e inventario conservan cuatro bases SQLite independientes. SQLite es persistencia real; su archivo necesita almacenamiento persistente si se traslada a un servidor.
- Se acordó migrar también esas cuatro bases a la nube más adelante. Es una decisión de destino; la migración aún no se ha realizado ni se autoriza como parte de esta subida de código.
- Se migraron los datos anteriores a las dos bases PostgreSQL con respaldo local y comprobaciones de conservación. Las credenciales quedan en `.env`, excluido de Git; cada servicio recibe su conexión correspondiente.
- Se incorporaron outbox, recepción idempotente de eventos, reintentos de avisos y recuperación de reservas/cancelaciones cuando Inventario vuelve a responder.

### Correo

- Se configuró Gmail mediante TLS y contraseña de aplicación. Después de una prueba inicial, el remitente se cambió a una cuenta dedicada a Hotels.
- Gmail aceptó los mensajes de comprobación y el usuario confirmó que las notificaciones llegan a Gmail.
- Los avisos implementados corresponden a bienvenida, confirmación y cancelación de reservas. La aceptación SMTP es un estado del proveedor y no garantiza por sí sola la entrega en bandeja de entrada.
- No guardar contraseñas de aplicación, contraseñas de bases, cookies ni tokens en este historial, capturas, repositorio o documento de entrega. Una captura de recepción para anexar a la entrega sigue pendiente.

### Verificación ya registrada

- Integración: 57 comprobaciones con SQLite temporal y otras 57 con dos PostgreSQL y cuatro SQLite temporales. SMTP desactivado en las dos modalidades.
- Configuración de bases: seis pruebas. Migración: tres pruebas.
- Hay `Dockerfile` y `compose.yaml`; la ejecución real con Docker sigue pendiente. La ejecución confirmada hasta ahora usa procesos Python locales.
- Los resultados detallados y sus límites se documentan en [PRUEBAS.md](PRUEBAS.md).

### Presentación y publicación

- Se sustituyeron las etiquetas repetidas de «práctica» y «simulado» en los flujos principales por textos de cuenta, habitaciones, reservas y avisos. La aclaración del proyecto se concentra en Información y referencias y en el pie del correo; no se eliminó la atribución de las fotografías.
- Los textos nuevos de correo se aplican a eventos nuevos; no se reescriben ni reenvían mensajes históricos.
- Se consultaron las restricciones de alojamiento gratuito. Vercel se considera para el frontend futuro; Render gratuito no permite el SMTP actual ni volúmenes persistentes para SQLite. Esta evaluación no es una contratación ni un despliegue.
- Se suspendieron temporalmente las subidas para priorizar el desarrollo local. Después el usuario reautorizó actualizar GitHub para llevar un historial de los avances. **GitHub queda autorizado; el despliegue y la migración de las cuatro bases restantes siguen pendientes.** Subir el código no publica credenciales ni datos de las bases.

## Guía y entregables

La guía original se leyó completa; se exportó una copia de consulta a PDF de nueve páginas para revisar también el diseño y las secciones finales. El original es un DOCX. No se modificó.

La sección de entregables pide: código fuente; repositorio e historial Git; README; Docker Compose; Swagger/OpenAPI; diagrama general de arquitectura; diagrama de comunicación; modelo de datos por servicio; decisiones técnicas; plan y evidencias de pruebas; manual breve de instalación y uso; presentación; y demostración funcional.

Queda pendiente completar la documentación OpenAPI, verificar Docker, formalizar los dos diagramas y los modelos de datos, preparar el manual y la presentación y reunir las evidencias. Las sesiones opacas deben justificarse como alternativa a JWT y la outbox con entrega HTTP como comunicación asíncrona elegida. La existencia de seis servicios no completa por sí sola todos los entregables.

## Orden de trabajo acordado

1. Terminar y revisar el frontend: navegación, formularios, estados vacíos y de error, fechas, vistas móviles y escritorio y coherencia del flujo completo.
2. Completar los microservicios y sus bases individuales, comprobar persistencia, aislamiento y recuperación de fallos. El catálogo y Habitaciones tienen consultas; la administración con permisos de edición no está implementada.
3. Completar documentación, contratos de API y verificación con contenedores para que la entrega sea reproducible.
4. Registrar en GitHub cada conjunto de avances terminado, revisado y probado, excluyendo secretos y datos personales. Elegir más adelante un despliegue gratuito compatible con la arquitectura y migrar las cuatro bases restantes, documentando sus límites.

Las decisiones y propuestas se detallan en [DECISIONES_TECNICAS.md](DECISIONES_TECNICAS.md). Este registro no reemplaza el historial real de commits ni inventa publicaciones que no se hicieron.
