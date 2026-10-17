-- Ejecutar como administrador. La contraseña se aprovisiona por separado.
CREATE ROLE hotels_auth_app NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS CONNECTION LIMIT 10;
GRANT CONNECT ON DATABASE postgres TO hotels_auth_app;
GRANT USAGE ON SCHEMA hotels_auth, hotels_meta TO hotels_auth_app;
GRANT SELECT ON hotels_meta.service_owner TO hotels_auth_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA hotels_auth TO hotels_auth_app;
CREATE POLICY backend_owner_read ON hotels_meta.service_owner FOR SELECT TO hotels_auth_app USING (service='auth');
CREATE POLICY backend_service_access ON hotels_auth.users FOR ALL TO hotels_auth_app USING (true) WITH CHECK (true);
CREATE POLICY backend_service_access ON hotels_auth.sessions FOR ALL TO hotels_auth_app USING (true) WITH CHECK (true);
CREATE POLICY backend_service_access ON hotels_auth.outbox FOR ALL TO hotels_auth_app USING (true) WITH CHECK (true);
