# 8. Manual de instalación y de usuario

## Parte A. Instalación

### Requisitos

- Windows 10 u 11, macOS o Linux.
- Python 3.12 o superior.
- Git.
- Opcional: Docker Desktop, para la opción con contenedores.
- Opcional: Node.js 22, solo para correr ESLint y las pruebas del frontend.

### Paso 1. Obtener el código

```powershell
git clone https://github.com/DodyCe/hotels.git
cd hotels
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

En macOS o Linux el intérprete es `.venv/bin/python`.

### Paso 2. Configurar `.env`

```powershell
Copy-Item .env.example .env
```

No reemplaces un `.env` que ya exista. Las variables principales:

| Variable | Para qué | Si se deja vacía |
|---|---|---|
| `AUTH_DATABASE_URL`, `NOTIFICATIONS_DATABASE_URL`, `RESERVATIONS_DATABASE_URL`, `CATALOG_DATABASE_URL`, `ROOMS_DATABASE_URL`, `AVAILABILITY_DATABASE_URL` | Conexión de cada servicio a su proyecto Supabase (Session pooler, puerto 5432) | Ese servicio usa SQLite local en `data/` |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_SECURITY`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` | Envío de correo por Gmail. La contraseña es de aplicación, no la normal | Los avisos quedan solo en la web |
| `MAIL_PROVIDER` | `smtp` o `gmail_api` | `smtp` |
| `INTERNAL_API_KEY` | Clave entre servicios, mínimo 32 caracteres | `start.py` genera una; Docker la exige |
| `PUBLIC_ORIGIN` | Dirección base de los enlaces de recuperación | `http://127.0.0.1:8080` |
| `COOKIE_SECURE` | `1` en HTTPS | Cookie sin `Secure` (correcto en local) |

Sin ninguna variable, la aplicación funciona completa en local con SQLite y sin envío de correo. Es la forma más rápida de probarla.

**Importante:** la versión publicada usa las seis bases de Supabase. No inicies una copia local con esas mismas URLs mientras la publicada esté activa: los hilos de fondo de las dos copias procesarían las mismas colas de eventos y correos. Para pruebas locales deja las URLs de base vacías.

**Nunca subas `.env` a GitHub.** Ya está en `.gitignore`.

### Paso 3, opción 1. Iniciar en Windows

Doble clic en `INICIAR.cmd`, o:

```powershell
.\.venv\Scripts\python.exe start.py
```

La consola muestra los seis servicios al iniciar y luego el Gateway. Déjala abierta. `Ctrl+C` detiene todo.

### Paso 3, opción 2. Iniciar con Docker Compose

1. En `.env`, define `INTERNAL_API_KEY` con 32 caracteres o más.
2. Ejecuta:

```powershell
docker compose up --build
```

3. Comprueba que los siete contenedores estén `healthy`:

```powershell
docker compose ps
```

4. Para detener: `docker compose down`. No uses `-v` si quieres conservar los datos SQLite de los volúmenes.

Solo el Gateway publica el puerto 8080. Los servicios se hablan por la red interna de Docker.

### Paso 4. Comprobar que funciona

| Dirección | Qué debe mostrar |
|---|---|
| <http://127.0.0.1:8080/> | La aplicación |
| <http://127.0.0.1:8080/status.html> | Seis servicios en **Activo** |
| <http://127.0.0.1:8080/docs.html> | Swagger UI con la API pública e interna |
| <http://127.0.0.1:8080/admin.html> | Panel de administración (requiere rol admin) |

En la versión publicada las mismas páginas están en https://hotels-monteria-dodyce.vercel.app/.

Desde otra terminal se puede correr el flujo completo automático:

```powershell
.\.venv\Scripts\python.exe tools/demo_flujo.py
```

Registra una cuenta, consulta hoteles y disponibilidad, reserva, cancela y revisa los avisos. Imprime cada paso con su código HTTP.

### Paso 5. Crear un administrador

1. Registra una cuenta normal desde la web.
2. En otra terminal, en la carpeta del proyecto, ejecuta:

```powershell
.\.venv\Scripts\python.exe tools/set_admin.py --email correo@ejemplo.com
```

3. La sesión anterior de esa cuenta se cierra. Inicia sesión otra vez y aparece el enlace **Administración** en el menú.

### Problemas frecuentes

| Problema | Solución |
|---|---|
| "No se puede acceder a este sitio" | La consola de `INICIAR.cmd` está cerrada o el inicio falló. Ábrela otra vez y lee el mensaje |
| Un servicio no inicia | Otro programa usa uno de los puertos 8080 u 8101 a 8106 |
| Un servicio aparece "Sin respuesta" en `/status.html` | Revisa su URL en `.env`. Una URL inválida detiene ese servicio con un error claro |
| Los correos no llegan | Revisa las variables `SMTP_*` y la carpeta de spam. `python tools/test_smtp.py` revisa la configuración sin enviar |
| Cambié `.env` y no pasa nada | Reinicia la aplicación |
| Docker dice que falta `INTERNAL_API_KEY` | Defínela en `.env` con 32 caracteres o más |

## Parte B. Uso para el huésped

### Buscar alojamiento

1. En la página principal elige **llegada**, **salida** y **número de huéspedes**. El destino es Montería.
2. Pulsa **Buscar estancia**. Se muestran los hoteles con habitaciones disponibles en esas fechas.
3. Filtra por servicios (Wi-Fi, Restaurante, Zona de trabajo), por precio máximo, u ordena por **Menor precio**.
4. Elige el tipo de habitación. El panel **Tu estancia** muestra el total: tarifa por noche por número de noches.

### Crear una cuenta o iniciar sesión

1. Pulsa **Ingresar** o **Registrarse**.
2. Para registrarte escribe nombre, correo y una contraseña de al menos 10 caracteres.
3. Quedas con la sesión iniciada y recibes el aviso de bienvenida.

Si te equivocas de contraseña, la aplicación muestra los intentos que quedan. Al sexto fallo la cuenta se bloquea 15 minutos.

### Recuperar la contraseña

1. En la ventana de ingreso pulsa **Olvidé mi contraseña** y escribe tu correo.
2. Abre el enlace que llega al correo. Vence en 15 minutos y sirve una sola vez.
3. Escribe y confirma la nueva contraseña. Las sesiones abiertas se cierran.

### Reservar

1. Con una habitación elegida, pulsa **Continuar con la reserva**.
2. Revisa el resumen y pulsa **Confirmar reserva**.
3. Verás la reserva confirmada con un código como `HT-2303AF5F07` y llegará el aviso de confirmación.

Si ya no hay cupo para esas fechas, la aplicación lo indica. Si un servicio está ocupado, la reserva puede quedar **Pendiente** unos segundos y se confirma sola.

**El proyecto es académico. No se cobra ni se reserva en los hoteles reales.**

### Consultar y cancelar reservas

1. Pulsa **Mis reservas**. Aparecen en tres grupos: **Próximas y en curso**, **Pasadas** y **Canceladas y rechazadas**.
2. Para cancelar pulsa **Cancelar reserva** y confirma con **Sí, cancelar**. El cupo queda libre y llega el aviso de cancelación.

### Ver avisos

Pulsa la campana. Cada aviso muestra asunto, contenido y estado de envío:

| Estado | Significado |
|---|---|
| Disponible en Hotels | El correo no está configurado; el aviso solo se ve aquí |
| En cola / Reintentando entrega | Se está enviando |
| Aceptado por el proveedor de correo | Gmail lo recibió. Revisa también la carpeta de spam |
| No se pudo entregar | Falló después de cinco intentos |

### Mi cuenta

**Mi cuenta** muestra nombre, fecha de registro y un resumen de reservas. Desde ahí se cierra sesión.

## Parte C. Uso para el administrador

Entra a **Administración** (o `/admin.html`). Tiene tres pestañas: **Hoteles**, **Habitaciones** y **Huéspedes**.

- **Hoteles:** **Nuevo hotel** abre el formulario (nombre, zona, dirección, descripción, servicios, comodidades). Cada fila permite editar, **Retirar** o **Reactivar**. Un hotel retirado deja de mostrarse y no acepta reservas nuevas; sus reservas anteriores se conservan.
- **Habitaciones:** pulsa **Ver habitaciones** en la tarjeta del hotel que quieres gestionar. Allí puedes editar, retirar o reactivar sus habitaciones y ajustar el **Inventario**. **Nueva habitación** crea un tipo de habitación en ese hotel con su capacidad, tarifa y unidades iniciales. El inventario no puede bajar de las unidades comprometidas por reservas vigentes. Usa **Volver a los hoteles** para elegir otro.
- **Huéspedes:** **Nuevo huésped** crea un perfil sin contraseña. Retirar un huésped con cuenta cierra sus sesiones y le impide entrar. Las cuentas administradoras no se pueden retirar desde aquí.

**Actualizar** recarga la lista. Una cuenta sin rol admin ve "Acceso restringido".

## Parte D. Uso de la API

1. Abre <http://127.0.0.1:8080/docs.html>.
2. Elige una operación, pulsa **Try it out** y luego **Execute**.
3. Para las rutas con sesión, inicia sesión en Hotels en otra pestaña del mismo navegador, o ejecuta `POST /auth/login` en Swagger. El navegador envía la cookie en las llamadas siguientes.
4. El selector superior cambia al contrato interno. Ese contrato se puede leer pero no ejecutar desde el navegador.

Los contratos están en [openapi.yaml](openapi.yaml) e [internal-openapi.yaml](internal-openapi.yaml).

## Parte E. Aplicación publicada

La aplicación está publicada en https://hotels-monteria-dodyce.vercel.app/ (Swagger en `/docs.html` y estado en `/status.html`). El frontend está en Vercel; el Gateway y los seis microservicios, en siete servicios gratuitos de Render; las bases, en Supabase.

En el plan gratuito los servicios se duermen sin uso, y el Gateway no alcanza a despertarlos por sí solo: mientras duermen, la página muestra errores y `/status.html` los marca **Sin respuesta**. Para despertarlos, abre estas direcciones (cada una puede tardar hasta un minuto en responder):

- https://hotels-auth.onrender.com/health
- https://hotels-notifications.onrender.com/health
- https://hotels-reservations-xqt7.onrender.com/health
- https://hotels-catalog.onrender.com/health
- https://hotels-rooms.onrender.com/health
- https://hotels-availability.onrender.com/health

Cuando las seis respondan `"status": "ok"`, `/status.html` muestra los seis en **Activo** y la aplicación funciona. Se vuelven a dormir tras unos 15 minutos sin uso.

Cómo se publicó, por si hay que repetirlo:

1. En Render, crear el Blueprint desde `render.yaml`. Se crean siete servicios y el grupo de variables `hotels-runtime`.
2. Completar en Render las seis URL de base, `INTERNAL_API_KEY`, `ORIGIN_SECRET`, `PUBLIC_ORIGIN` y las variables de Gmail API (`MAIL_PROVIDER=gmail_api`, `GMAIL_CLIENT_ID`, `GMAIL_CLIENT_SECRET`, `GMAIL_REFRESH_TOKEN`). `tools/authorize_gmail.py` obtiene el token.
3. En Vercel, importar el repositorio y definir `HOTELS_GATEWAY_URL` y `ORIGIN_SECRET`.
4. Comprobar `https://<dominio>/status.html` y el flujo completo.

El detalle está en la sección 19 de [README_CONTEXT.md](../README_CONTEXT.md).
