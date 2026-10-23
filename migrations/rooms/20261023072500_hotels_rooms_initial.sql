-- Aplicar únicamente en el proyecto de Habitaciones. Sin claves foráneas entre proyectos.
BEGIN;
CREATE SCHEMA IF NOT EXISTS hotels_meta;
REVOKE ALL ON SCHEMA hotels_meta FROM PUBLIC, anon, authenticated;
CREATE TABLE IF NOT EXISTS hotels_meta.service_owner(id INTEGER PRIMARY KEY CHECK(id=1), service TEXT NOT NULL);
INSERT INTO hotels_meta.service_owner VALUES (1,'rooms') ON CONFLICT(id) DO NOTHING;
DO $$ BEGIN
  IF (SELECT service FROM hotels_meta.service_owner WHERE id=1) <> 'rooms' THEN
    RAISE EXCEPTION 'La base pertenece a otro microservicio';
  END IF;
END $$;
ALTER TABLE hotels_meta.service_owner ENABLE ROW LEVEL SECURITY;
CREATE SCHEMA hotels_rooms;
REVOKE ALL ON SCHEMA hotels_rooms FROM PUBLIC, anon, authenticated;
CREATE TABLE hotels_rooms.rooms(
  id TEXT PRIMARY KEY,
  "hotelId" TEXT NOT NULL,
  name TEXT NOT NULL,
  capacity INTEGER NOT NULL CHECK(capacity BETWEEN 1 AND 20),
  price BIGINT NOT NULL CHECK(price>=0),
  sort_order INTEGER NOT NULL CHECK(sort_order>=0)
);
CREATE INDEX rooms_hotel_capacity ON hotels_rooms.rooms("hotelId",capacity);
ALTER TABLE hotels_rooms.rooms ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON ALL TABLES IN SCHEMA hotels_rooms FROM PUBLIC, anon, authenticated;
REVOKE ALL ON hotels_meta.service_owner FROM PUBLIC, anon, authenticated;
CREATE ROLE hotels_rooms_app NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS CONNECTION LIMIT 10;
GRANT CONNECT ON DATABASE postgres TO hotels_rooms_app;
GRANT USAGE ON SCHEMA hotels_rooms,hotels_meta TO hotels_rooms_app;
GRANT SELECT ON hotels_meta.service_owner TO hotels_rooms_app;
GRANT SELECT,INSERT ON hotels_rooms.rooms TO hotels_rooms_app;
CREATE POLICY backend_owner_read ON hotels_meta.service_owner FOR SELECT TO hotels_rooms_app USING(service='rooms');
CREATE POLICY backend_rooms_read ON hotels_rooms.rooms FOR SELECT TO hotels_rooms_app USING(true);
CREATE POLICY backend_rooms_seed ON hotels_rooms.rooms FOR INSERT TO hotels_rooms_app WITH CHECK(true);
DO $$ BEGIN
  IF to_regprocedure('public.rls_auto_enable()') IS NOT NULL THEN
    REVOKE EXECUTE ON FUNCTION public.rls_auto_enable() FROM PUBLIC, anon, authenticated;
  END IF;
END $$;
COMMIT;
