-- Usuarios y huéspedes pertenecen exclusivamente al dominio de Autenticación.
BEGIN;
ALTER TABLE hotels_auth.users ADD COLUMN role TEXT NOT NULL DEFAULT 'guest' CHECK(role IN ('guest','admin'));
ALTER TABLE hotels_auth.users ADD COLUMN active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1));
CREATE TABLE hotels_auth.guests(
    id TEXT PRIMARY KEY,
    user_id TEXT UNIQUE REFERENCES hotels_auth.users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,email TEXT NOT NULL UNIQUE,phone TEXT NOT NULL DEFAULT '',
    active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)),created DOUBLE PRECISION NOT NULL
);
INSERT INTO hotels_auth.guests(id,user_id,name,email,created) SELECT id,id,name,email,created FROM hotels_auth.users;
ALTER TABLE hotels_auth.guests ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON hotels_auth.guests FROM PUBLIC,anon,authenticated;
GRANT SELECT,INSERT,UPDATE,DELETE ON hotels_auth.guests TO hotels_auth_app;
CREATE POLICY backend_service_access ON hotels_auth.guests FOR ALL TO hotels_auth_app USING(true) WITH CHECK(true);
COMMIT;
