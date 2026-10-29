# Hotels

Sistema de reservas hoteleras del proyecto 6, con frontend HTML/CSS/JavaScript, API Gateway y seis microservicios Python con bases independientes.

**Documentación central:** [README_CONTEXT.md](README_CONTEXT.md). Incluye instalación, herramientas, arquitectura, seguridad, Supabase, correo, APIs, pruebas, decisiones, historial, créditos y pendientes de la guía.

Para iniciar en Windows, ejecuta `INICIAR.cmd` y abre <http://127.0.0.1:8080/>. Mantén la consola abierta.

El panel está en <http://127.0.0.1:8080/admin.html> y requiere una cuenta con rol administrador. La documentación interactiva de la API está en <http://127.0.0.1:8080/docs.html>.

Las credenciales se configuran en el `.env` privado, nunca en Git. Los hoteles son referencias independientes y las fotos son ilustrativas; los avisos y créditos completos se conservan en el contexto y la interfaz. El despliegue público sigue pendiente.

La configuración preparada para Vercel (`vercel.ts`) y siete servicios gratuitos de Render (`render.yaml`), sus variables y el correo HTTPS se explican en la sección 19 del contexto.
