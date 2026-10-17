-- Ejecutar como administrador. La contraseña se aprovisiona por separado.
CREATE ROLE hotels_notifications_app NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS CONNECTION LIMIT 10;
GRANT CONNECT ON DATABASE postgres TO hotels_notifications_app;
GRANT USAGE ON SCHEMA hotels_notifications, hotels_meta TO hotels_notifications_app;
GRANT SELECT ON hotels_meta.service_owner TO hotels_notifications_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA hotels_notifications TO hotels_notifications_app;
CREATE POLICY backend_owner_read ON hotels_meta.service_owner FOR SELECT TO hotels_notifications_app USING (service='notifications');
CREATE POLICY backend_service_access ON hotels_notifications.messages FOR ALL TO hotels_notifications_app USING (true) WITH CHECK (true);
