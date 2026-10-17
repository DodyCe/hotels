-- Solo en el proyecto hotels-notifications. Nunca en el de Autenticación.
CREATE SCHEMA IF NOT EXISTS hotels_meta;
REVOKE ALL ON SCHEMA hotels_meta FROM PUBLIC;
CREATE TABLE IF NOT EXISTS hotels_meta.service_owner (
    id INTEGER PRIMARY KEY CHECK (id=1), service TEXT NOT NULL
);
INSERT INTO hotels_meta.service_owner VALUES (1, 'notifications') ON CONFLICT (id) DO NOTHING;
DO $$ BEGIN
    IF (SELECT service FROM hotels_meta.service_owner WHERE id=1) <> 'notifications' THEN
        RAISE EXCEPTION 'La base pertenece a otro microservicio';
    END IF;
END $$;
ALTER TABLE hotels_meta.service_owner ENABLE ROW LEVEL SECURITY;
CREATE SCHEMA IF NOT EXISTS hotels_notifications;
REVOKE ALL ON SCHEMA hotels_notifications FROM PUBLIC;
CREATE TABLE IF NOT EXISTS hotels_notifications.messages (
    id TEXT PRIMARY KEY, user_id TEXT NOT NULL, recipient TEXT NOT NULL,
    subject TEXT NOT NULL, body TEXT NOT NULL, status TEXT NOT NULL,
    created DOUBLE PRECISION NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
    next_try DOUBLE PRECISION NOT NULL DEFAULT 0
);
ALTER TABLE hotels_notifications.messages ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON ALL TABLES IN SCHEMA hotels_notifications FROM PUBLIC;
