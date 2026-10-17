# Decisiones técnicas de Hotels

Actualización: 17 de octubre de 2026. «Implementada» describe el código local; no implica que el cambio esté publicado. Las propuestas de alojamiento aún no están aprobadas ni desplegadas.

## 01. Seis dominios con persistencia propia — implementada

Se separan Autenticación (8101), Notificaciones (8102), Reservas (8103), Catálogo de hoteles (8104), Habitaciones (8105) y Disponibilidad e inventario (8106). Cada servicio tiene proceso, API y base independientes.

La razón es asignar a cada dominio una responsabilidad y un dueño de los datos: una habitación y su tarifa pertenecen a Habitaciones; la ocupación por noche pertenece a Inventario; la operación y su estado pertenecen a Reservas. Ningún servicio consulta tablas de otro. Guardar identificadores o una copia histórica de los nombres y del importe de una reserva no convierte las bases en compartidas.

Autenticación usa PostgreSQL en `hotels-auth`; Notificaciones usa PostgreSQL en `hotels-notifications`. Son proyectos distintos en Supabase. Reservas usa `reservations.sqlite3`, Catálogo `catalog.sqlite3`, Habitaciones `rooms.sqlite3` e Inventario `availability.sqlite3`. Los cuatro archivos también son bases propias; no están alojados en Supabase.

El límite actual es operativo: SQLite requiere disco persistente y las escrituras se coordinan dentro de cada servicio. Cambiar el proveedor no obliga a unir las bases ni a crear un séptimo servicio.

El destino acordado es tener las seis bases en la nube. La migración de las cuatro SQLite queda para una etapa posterior; no forma parte de la actualización actual de GitHub.

## 02. Gateway como entrada del backend — implementada

El navegador consume `/api` mediante el Gateway en 8080. El backend está formado por los seis servicios y ese Gateway; no existe otro «backend» independiente que deba contenerlos todos.

Esta entrada centraliza el enrutamiento y las comprobaciones de origen y mantiene la clave interna fuera del navegador. Se necesita verificar correctamente hosts, origen público y cookies seguras al pasar a HTTPS.

## 03. Un repositorio, procesos y bases separados — implementada

El monorepositorio permite revisar juntos los contratos, semillas, pruebas y cambios coordinados. No obliga a ejecutar todos los servicios en un solo proceso. El Compose describe componentes separados; su arranque aún debe verificarse con Docker.

En un alojamiento futuro podrán compartir una máquina y seguir siendo servicios independientes. Si se selecciona una plataforma con despliegue por servicio, cada proceso deberá tener su propia configuración. Ejecutar únicamente `start.py` dentro de una instancia no equivale a haber comprobado despliegues independientes.

## 04. Sesiones opacas y contraseñas derivadas — implementada

Se usa scrypt con sal por usuario y una sesión aleatoria cuyo hash se persiste en Autenticación. La sesión caduca a las ocho horas y la cookie es HttpOnly y SameSite=Strict. Se eligió esta alternativa a JWT para permitir revocación central inmediata al cerrar sesión y mantener sencillo el flujo del navegador.

La consecuencia es que los servicios deben consultar Autenticación para validar la sesión. La guía permite una alternativa a JWT si está justificada. Recuperación de contraseña y verificación de titularidad del correo no están implementadas; no deben anunciarse como disponibles.

## 05. Outbox, APIs HTTP e idempotencia — implementada

Auth y Reservas guardan el evento en su propia outbox junto con la operación de negocio. Un trabajador entrega el evento por HTTP y reintenta ante fallos; Notificaciones evita duplicados por identificador de evento y consulta el destinatario en Auth.

La razón es desacoplar la disponibilidad del correo de la transacción de cuenta o reserva sin incorporar todavía un broker adicional. No se utiliza Kafka ni RabbitMQ. La entrega es eventual y SMTP no puede garantizar exactamente una vez si una conexión falla después de que el proveedor haya aceptado el correo. Las pruebas incluyen indisponibilidad y recuperación de Inventario.

## 06. PostgreSQL administrado para dos dominios — implementada

Se eligieron dos proyectos Supabase gratuitos, uno por dominio, empezando por Autenticación y Notificaciones según la elección del usuario. Las conexiones solo están en el backend, con roles de aplicación limitados. La migración respalda los archivos anteriores y comprueba la conservación de los datos.

El backend utiliza PostgreSQL; no se está usando el producto Supabase Auth para autenticar las cuentas de Hotels. No se comparte una única base remota entre los dos servicios para presentar una independencia inexistente.

## 07. Gmail SMTP configurable — implementada y recepción confirmada por el usuario

El envío usa una cuenta dedicada a Hotels, TLS y contraseña de aplicación en `.env`. Permite cambiar de proveedor sin introducir secretos en HTML ni JavaScript. Las notificaciones de bienvenida, confirmación y cancelación toman el destinatario de la cuenta autenticada.

El estado mostrado por la aplicación distingue la aceptación del proveedor de la recepción en bandeja. El usuario confirmó la llegada en Gmail; una captura para el informe sigue pendiente. Los mensajes históricos no se reescriben ni se reenvían al cambiar el diseño de la plantilla.

## 08. Presentación profesional y referencias transparentes — implementada en los textos

La interfaz utiliza lenguaje de producto: habitaciones, estancia, reservas y notificaciones. Se retiraron las etiquetas repetidas de «práctica». La aclaración de independencia del proyecto y de los datos de ejemplo permanece en Información y referencias y en el pie de los correos; las fotos conservan sus créditos y la indicación de que son ilustrativas.

La razón es ofrecer una experiencia coherente sin atribuir a los hoteles ofertas, autorizaciones o reservas que no han emitido. La mejora del texto no demuestra que todo el frontend esté terminado ni que exista integración comercial con los establecimientos.

## 09. Presupuesto gratuito y evaluación de alojamiento — restricción aceptada, destino pendiente

El usuario exige costo cero. El despliegue público está detenido hasta terminar el frontend y los servicios con sus bases. El código sí puede versionarse en GitHub para registrar avances. No se ha desplegado nada como resultado de esta evaluación.

**Frontend:** Vercel es una opción por evaluar para los archivos de `web/`. El navegador usa `/api`; separar el dominio del frontend exige configurar una reescritura externa hacia el Gateway y verificar cookies, origen permitido y HTTPS. Publicar los archivos estáticos por sí solos no publica la funcionalidad del backend. Véanse las [reescrituras externas de Vercel](https://vercel.com/docs/rewrites) y su [soporte de monorepositorios](https://vercel.com/docs/monorepos).

**Backend en Render gratuito:** no es compatible con el diseño actual sin cambios. Sus instancias gratuitas bloquean salida SMTP por 25, 465 y 587, así que Gmail SMTP no funcionaría allí. Tampoco admiten discos persistentes y su sistema de archivos es efímero, por lo que las cuatro SQLite locales perderían datos. Las 750 horas gratuitas son compartidas por el espacio de trabajo y las instancias se suspenden tras 15 minutos sin tráfico entrante; no deben presupuestarse siete procesos siempre encendidos como siete cuotas gratuitas completas. Véanse las [limitaciones oficiales de Render gratuito](https://render.com/docs/free) y el [anuncio del bloqueo SMTP](https://render.com/changelog/free-web-services-will-no-longer-allow-outbound-traffic-to-smtp-ports).

**Separación del despliegue:** Render permite desplegar componentes de un mismo repositorio como servicios distintos; eso no elimina las restricciones anteriores. Cualquier selección futura debe comprobar persistencia, conectividad entre servicios, SMTP y límites totales, además de adaptar el enlace a `0.0.0.0` y el puerto de la plataforma. Véanse [monorepositorios en Render](https://render.com/docs/monorepo-support) y [Web Services](https://render.com/docs/web-services).

La ejecución local sigue siendo el entorno verificado mientras se termina el sistema. No se ha elegido una alternativa definitiva de alojamiento público gratuito; tampoco se ha aprobado pagar por evitar estas restricciones. Esta decisión se retomará cuando corresponda publicar.

## 10. Control de cambios y evidencias — instrucción vigente

Después de una pausa temporal de subidas, el usuario autorizó el 17 de octubre actualizar GitHub con los avances para conservar el historial requerido por la guía. La instrucción vigente es **versionar los cambios terminados y verificados**. Esta autorización no incluye desplegar la aplicación ni migrar todavía las cuatro bases SQLite a la nube.

Cada conjunto coherente debe estar terminado, revisado y probado antes de subirlo. `.env`, bases de usuarios, respaldos y entornos virtuales quedan fuera de Git. Los resultados de pruebas y las limitaciones se documentan en [PRUEBAS.md](PRUEBAS.md); los hitos e instrucciones del proyecto quedan en [HISTORIAL_PROYECTO.md](HISTORIAL_PROYECTO.md). La subida se verifica comparando los commits locales y remotos; tener archivos locales no demuestra que ya estén en GitHub.
