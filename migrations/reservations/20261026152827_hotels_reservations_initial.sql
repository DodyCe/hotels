-- Proyecto exclusivo de Reservas. Las credenciales se aprovisionan por separado.
BEGIN;
CREATE SCHEMA IF NOT EXISTS hotels_meta;
REVOKE ALL ON SCHEMA hotels_meta FROM PUBLIC, anon, authenticated;
CREATE TABLE IF NOT EXISTS hotels_meta.service_owner(id INTEGER PRIMARY KEY CHECK(id=1),service TEXT NOT NULL);
INSERT INTO hotels_meta.service_owner VALUES (1,'reservations') ON CONFLICT(id) DO NOTHING;
DO $$ BEGIN
  IF (SELECT service FROM hotels_meta.service_owner WHERE id=1) <> 'reservations' THEN
    RAISE EXCEPTION 'La base pertenece a otro microservicio';
  END IF;
END $$;
ALTER TABLE hotels_meta.service_owner ENABLE ROW LEVEL SECURITY;
CREATE SCHEMA hotels_reservations;
REVOKE ALL ON SCHEMA hotels_reservations FROM PUBLIC, anon, authenticated;
CREATE TABLE hotels_reservations.reservations(
  id TEXT PRIMARY KEY, user_id TEXT NOT NULL, hotel_id TEXT NOT NULL,
  checkin TEXT NOT NULL, checkout TEXT NOT NULL,
  guests INTEGER NOT NULL CHECK(guests BETWEEN 1 AND 20),
  total BIGINT NOT NULL CHECK(total>=0),
  status TEXT NOT NULL CHECK(status IN ('Pendiente','Confirmada','Cancelando','Cancelada','Rechazada')),
  created DOUBLE PRECISION NOT NULL,
  room_id TEXT NOT NULL DEFAULT '', hotel_name TEXT NOT NULL DEFAULT '', room_name TEXT NOT NULL DEFAULT '',
  inventory_synced INTEGER NOT NULL DEFAULT 0 CHECK(inventory_synced IN (0,1))
);
CREATE INDEX reservations_user_created ON hotels_reservations.reservations(user_id,created DESC);
CREATE TABLE hotels_reservations.outbox(
  id TEXT PRIMARY KEY,body TEXT NOT NULL,
  attempts INTEGER NOT NULL DEFAULT 0,next_try DOUBLE PRECISION NOT NULL DEFAULT 0,
  delivered INTEGER NOT NULL DEFAULT 0 CHECK(delivered IN (0,1))
);
ALTER TABLE hotels_reservations.reservations ENABLE ROW LEVEL SECURITY;
ALTER TABLE hotels_reservations.outbox ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON ALL TABLES IN SCHEMA hotels_reservations FROM PUBLIC, anon, authenticated;
REVOKE ALL ON hotels_meta.service_owner FROM PUBLIC, anon, authenticated;
CREATE ROLE hotels_reservations_app NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS CONNECTION LIMIT 10;
GRANT CONNECT ON DATABASE postgres TO hotels_reservations_app;
GRANT USAGE ON SCHEMA hotels_reservations,hotels_meta TO hotels_reservations_app;
GRANT SELECT ON hotels_meta.service_owner TO hotels_reservations_app;
GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA hotels_reservations TO hotels_reservations_app;
CREATE POLICY backend_owner_read ON hotels_meta.service_owner FOR SELECT TO hotels_reservations_app USING(service='reservations');
CREATE POLICY backend_service_access ON hotels_reservations.reservations FOR ALL TO hotels_reservations_app USING(true) WITH CHECK(true);
CREATE POLICY backend_service_access ON hotels_reservations.outbox FOR ALL TO hotels_reservations_app USING(true) WITH CHECK(true);
DO $$ BEGIN
  IF to_regprocedure('public.rls_auto_enable()') IS NOT NULL THEN
    REVOKE EXECUTE ON FUNCTION public.rls_auto_enable() FROM PUBLIC, anon, authenticated;
  END IF;
END $$;
COMMIT;
