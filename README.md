# Hotels

Sistema de reservas hoteleras del proyecto 6, con frontend HTML/CSS/JavaScript, API Gateway y seis microservicios Python con bases PostgreSQL independientes.

Aplicación pública: [Hotels](https://hotels-monteria-dodyce.vercel.app/) · [Swagger](https://hotels-monteria-dodyce.vercel.app/docs.html) · [Estado](https://hotels-monteria-dodyce.vercel.app/status.html). El alcance de la verificación y los límites gratuitos/OAuth están en [README_CONTEXT.md](README_CONTEXT.md).

## Inicio rápido

En Windows, ejecuta `INICIAR.cmd` y abre <http://127.0.0.1:8080/>. Mantén la consola abierta.

Mientras la versión publicada esté activa, la copia local debe usar SQLite (URLs de base vacías en `.env`), no las mismas bases de Supabase.

Instalación nueva:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe start.py
```

Con Docker: define `INTERNAL_API_KEY` (32 caracteres o más) en `.env` y ejecuta `docker compose up --build`.

| Dirección | Contenido |
|---|---|
| <http://127.0.0.1:8080/> | Aplicación |
| <http://127.0.0.1:8080/docs.html> | Swagger UI, contratos público e interno |
| <http://127.0.0.1:8080/admin.html> | Panel de administración (rol admin) |
| <http://127.0.0.1:8080/status.html> | Estado de los seis microservicios |

Las credenciales se configuran en el `.env` privado, nunca en Git. Sin `.env`, todo funciona en local con SQLite y sin envío de correo.

## Entregables

| Documento | Contenido |
|---|---|
| [docs/00-requisitos-y-entregables.md](docs/00-requisitos-y-entregables.md) | Requisitos de la guía y dónde se cumple cada uno |
| [docs/01-arquitectura.md](docs/01-arquitectura.md) | Diagrama general, diagrama de comunicación y flujos |
| [docs/02-microservicios.md](docs/02-microservicios.md) | Responsabilidad, endpoints y códigos HTTP de cada servicio |
| [docs/03-modelo-de-datos.md](docs/03-modelo-de-datos.md) | Modelo de datos por servicio |
| [docs/04-decisiones-tecnicas.md](docs/04-decisiones-tecnicas.md) | Tecnologías y decisiones justificadas |
| [docs/05-seguridad.md](docs/05-seguridad.md) | Autenticación, roles, recuperación y protección de datos |
| [docs/06-logs-y-monitoreo.md](docs/06-logs-y-monitoreo.md) | Logs, salud y página de estado |
| [docs/07-plan-de-pruebas.md](docs/07-plan-de-pruebas.md) | Plan de pruebas y evidencias |
| [docs/08-manual-instalacion-y-usuario.md](docs/08-manual-instalacion-y-usuario.md) | Instalación, uso y despliegue |
| [docs/09-guion-sustentacion.md](docs/09-guion-sustentacion.md) | Guion de la sustentación y la demostración |
| [docs/openapi.yaml](docs/openapi.yaml), [docs/internal-openapi.yaml](docs/internal-openapi.yaml) | Contratos OpenAPI |
| [docs/evidencias/](docs/evidencias/) | Salidas de pruebas, logs y capturas |
| [compose.yaml](compose.yaml), [Dockerfile](Dockerfile) | Contenedores |

## Estructura

```text
gateway.py            API Gateway (8080)
services/             Seis microservicios (8101 a 8106) y código común
web/                  Frontend, panel admin, Swagger UI y página de estado
migrations/           SQL de cada base Supabase
seed/                 Datos iniciales
tests/                Pruebas automáticas
tools/                Demo del flujo, promoción de admin, migración y correo
docs/                 Entregables
```

## Más contexto

[README_CONTEXT.md](README_CONTEXT.md) conserva el historial completo del proyecto: configuración de Supabase, correo, verificaciones con fecha y decisiones de cada etapa. La publicación en Vercel (`vercel.ts`) y Render (`render.yaml`) se explica en su sección 19 y en la entrada del 2 de noviembre.

Los hoteles son referencias independientes y las fotos son ilustrativas; los créditos completos están en el contexto y en la interfaz.
