-- Solo en el proyecto hotels-auth. Nunca en el de Notificaciones.
CREATE SCHEMA IF NOT EXISTS hotels_meta;
REVOKE ALL ON SCHEMA hotels_meta FROM PUBLIC;
CREATE TABLE IF NOT EXISTS hotels_meta.service_owner (
    id INTEGER PRIMARY KEY CHECK (id=1), service TEXT NOT NULL
);
INSERT INTO hotels_meta.service_owner VALUES (1, 'auth') ON CONFLICT (id) DO NOTHING;
DO $$ BEGIN
    IF (SELECT service FROM hotels_meta.service_owner WHERE id=1) <> 'auth' THEN
        RAISE EXCEPTION 'La base pertenece a otro microservicio';
    END IF;
END $$;
ALTER TABLE hotels_meta.service_owner ENABLE ROW LEVEL SECURITY;
CREATE SCHEMA IF NOT EXISTS hotels_auth;
REVOKE ALL ON SCHEMA hotels_auth FROM PUBLIC;
CREATE TABLE IF NOT EXISTS hotels_auth.users (
    id TEXT PRIMARY KEY, name TEXT NOT NULL, email TEXT NOT NULL UNIQUE,
    salt TEXT NOT NULL, password_hash TEXT NOT NULL, created DOUBLE PRECISION NOT NULL
);
CREATE TABLE IF NOT EXISTS hotels_auth.sessions (
    token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES hotels_auth.users(id),
    expires DOUBLE PRECISION NOT NULL
);
CREATE TABLE IF NOT EXISTS hotels_auth.outbox (
    id TEXT PRIMARY KEY, body TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
    next_try DOUBLE PRECISION NOT NULL DEFAULT 0, delivered INTEGER NOT NULL DEFAULT 0
);
ALTER TABLE hotels_auth.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE hotels_auth.sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE hotels_auth.outbox ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON ALL TABLES IN SCHEMA hotels_auth FROM PUBLIC;
