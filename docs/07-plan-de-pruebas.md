# 7. Plan de pruebas y evidencias

## 7.1 Objetivo

Comprobar que los seis microservicios funcionan juntos a través del Gateway, que cada uno respeta su dominio y su base, y que el sistema se recupera cuando un servicio falla.

## 7.2 Tipos de prueba

| Suite | Archivo | Qué prueba | Resultado (2 nov 2026) |
|---|---|---|---|
| Integración | `tests/integration.py` | Levanta Gateway y seis servicios en puertos de prueba y recorre los flujos por HTTP | 121 de 121 |
| Configuración de bases | `tests/database_config.py` | Una conexión por servicio, sin bases compartidas, TLS y errores sin contraseñas | 11 de 11 |
| Migración | `tests/migration.py` | Respaldo, migración repetible y rollback ante conflictos | 9 de 9 |
| Contratos | `tests/openapi.py` | Los YAML son OpenAPI válidos y coinciden con las rutas del Gateway | 4 de 4 |
| Correo | `tests/security_email.py` | Contenido y cabeceras de los correos, sin datos sensibles | 5 de 5 |
| Nube | `tests/cloud_deployment.py` | `render.yaml`, `vercel.ts`, Gmail API y secretos por servicio | 12 de 12 |
| Frontend | `tests/frontend_build.mjs` | El artefacto web no incluye código del servidor ni secretos | Aprobada |
| Docker | `tests/compose.py` | Construye los siete contenedores y recorre el flujo entre ellos | 19 comprobaciones, en CI |
| Lint | `ruff`, ESLint, pre-commit | Errores de Python y JavaScript, YAML, JSON y claves privadas | Sin errores |

Las pruebas usan puertos 18080 y 18101 a 18106, bases SQLite temporales y el envío de correo desactivado. No tocan los datos reales.

**Con las bases reales:** `tests/integration.py --six-postgres` corre la misma suite contra los seis proyectos Supabase. Crea datos propios con fechas lejanas y los borra al terminar. La última ejecución reportada aprobó 104 comprobaciones (2 nov 2026). Debe correrse con Hotels detenido.

## 7.3 Casos por área

La lista completa de las 121 comprobaciones está en [evidencias/prueba-integration.txt](evidencias/prueba-integration.txt). Estos son los casos representativos.

### Autenticación y sesiones

| ID | Caso | Esperado |
|---|---|---|
| AU-01 | Registro de cuenta | 201 y cookie `HttpOnly`, `SameSite` |
| AU-02 | Correo repetido | 409 |
| AU-03 | Contraseña incorrecta | 401 con intentos restantes |
| AU-04 | Seis fallos seguidos | 429 y bloqueo de 15 minutos, aun tras reiniciar Auth |
| AU-05 | El bloqueo de un correo no afecta otra cuenta | La otra cuenta entra |
| AU-06 | Contraseña guardada | Hash scrypt con sal, nunca en texto |
| AU-07 | Cerrar sesión | La cookie anterior recibe 401 |
| AU-08 | Dos instancias de Auth con fallos simultáneos | Comparten el límite exacto de seis |

### Recuperación de contraseña

| ID | Caso | Esperado |
|---|---|---|
| RC-01 | Correo existente e inexistente | Misma respuesta 202 |
| RC-02 | Enlace inventado | 400, contraseña sin cambios |
| RC-03 | Enlace usado dos veces al mismo tiempo | Solo uno funciona |
| RC-04 | Enlace vencido | Rechazado |
| RC-05 | Cambio correcto | Cierra todas las sesiones y desbloquea la cuenta |

### Reservas e inventario

| ID | Caso | Esperado |
|---|---|---|
| RE-01 | Reserva válida | 201 `Confirmada`, cupo descontado |
| RE-02 | Total enviado por el cliente | Se ignora; se usa la tarifa del servidor |
| RE-03 | Dos reservas simultáneas por el último cupo | Solo una se confirma |
| RE-04 | Habitación de otro hotel o capacidad superada | 400 |
| RE-05 | Fechas inválidas o fuera de formato | 400 |
| RE-06 | Otro usuario cancela mi reserva | 404 |
| RE-07 | Cancelar dos veces | Mismo resultado, sin duplicar avisos |
| RE-08 | Cancelación | Cupo liberado; otro tipo no cambia |
| RE-09 | Dos procesos de Inventario a la vez | No hay sobreventa |

### Tolerancia a fallos

| ID | Caso | Esperado |
|---|---|---|
| TF-01 | Inventario detenido al reservar | 202 `Pendiente` |
| TF-02 | Inventario vuelve | La reserva pasa a `Confirmada` con un solo cupo |
| TF-03 | Inventario detenido al cancelar | Queda `Cancelando` |
| TF-04 | Inventario vuelve | Pasa a `Cancelada` y libera el cupo |
| TF-05 | Reiniciar Reservas | Las reservas siguen ahí |
| TF-06 | Inventario detenido al crear una habitación | 202, no se ofrece al público hasta tener unidades |

### Notificaciones

| ID | Caso | Esperado |
|---|---|---|
| NO-01 | Registro, reserva y cancelación | Llegan bienvenida, confirmación y cancelación |
| NO-02 | Correo destino enviado por el cliente | Se ignora; se usa el de Auth |
| NO-03 | Evento repetido | Un solo mensaje |
| NO-04 | Correo sin configurar | Vista previa en la web, sin envío |
| NO-05 | Correo de recuperación | No aparece en la bandeja web |

### Administración y permisos

| ID | Caso | Esperado |
|---|---|---|
| AD-01 | Huésped intenta listar huéspedes o crear hoteles | 403 |
| AD-02 | Registro público con `role: admin` | 400; el registro no acepta roles |
| AD-03 | Admin crea, edita, retira y reactiva hotel | 201, 200, 200, 200 |
| AD-04 | Admin crea habitación | Se crea su inventario por API |
| AD-05 | Reducir inventario por debajo de las reservas futuras | 409 |
| AD-06 | Hotel o habitación retirados | No se ofrecen ni aceptan reservas nuevas |
| AD-07 | Desactivar huésped con cuenta | Sus sesiones se revocan y no puede entrar |
| AD-08 | Desactivar una cuenta administradora | 409 |
| AD-09 | HTML en campos administrativos | 400 |

### Arquitectura

| ID | Caso | Esperado |
|---|---|---|
| AR-01 | Seis bases separadas | Cada servicio crea solo su base |
| AR-02 | Cada servicio con proceso y `/health` propios | 200 en cada puerto |
| AR-03 | `/api/internal/*` desde el navegador | No existe en el Gateway |
| AR-04 | Origen externo | 403 |

## 7.4 Cómo repetir las pruebas

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe tests/integration.py
.\.venv\Scripts\python.exe tests/database_config.py
.\.venv\Scripts\python.exe tests/migration.py
.\.venv\Scripts\python.exe tests/openapi.py
.\.venv\Scripts\python.exe tests/security_email.py
.\.venv\Scripts\python.exe tests/cloud_deployment.py
node tests/frontend_build.mjs
npm run lint
```

Con las seis bases reales (Hotels detenido y `.env` completo):

```powershell
.\.venv\Scripts\python.exe tests/integration.py --six-postgres
```

Docker (requiere Docker Desktop):

```powershell
python tests/compose.py
```

## 7.5 Integración continua

GitHub Actions (`.github/workflows/ci.yml`) corre en cada pull request y en cada cambio a `main`:

1. **Lint:** pre-commit con ruff, YAML, JSON, conflictos y claves privadas.
2. **Pruebas:** las seis suites de Python.
3. **Web:** ESLint, `node --check` y la prueba del artefacto frontend.
4. **Docker:** construye la imagen, levanta los siete contenedores y ejecuta `tests/compose.py`.

El equipo fusiona un pull request solo con los cuatro trabajos en verde. El historial está en la pestaña Actions del repositorio.

## 7.6 Evidencias

Carpeta [evidencias/](evidencias/):

| Archivo | Contenido |
|---|---|
| `prueba-*.txt` | Salida de cada suite con comando, fecha, entorno y código de salida |
| `flujo-demo.txt` | Salida de `tools/demo_flujo.py`: el flujo completo paso a paso |
| `logs-flujo-demo.txt` | Logs de los siete procesos durante ese flujo |
| `01-catalogo-y-resumen.jpg` | Catálogo, fechas y resumen de la reserva |
| `02-reserva-confirmada.jpg` | Reserva confirmada en "Mis reservas" |
| `03-swagger-ui.jpg` | Swagger UI en `/docs.html` |
| `04-estado-servicios.jpg` | Página de estado con los seis servicios activos |
| `05-panel-administracion.jpg` | Panel de administración |

Las evidencias de esta carpeta se tomaron con bases SQLite locales y el correo desactivado. Las de bases reales y correo recibido las debe añadir el equipo (ver [00-requisitos-y-entregables.md](00-requisitos-y-entregables.md)).

## 7.7 No cubierto

- Pruebas de carga.
- Pruebas automáticas de interfaz en navegador (se revisó manualmente en escritorio y móvil).
- Despliegue público en Vercel y Render.
