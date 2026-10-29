-- Proyecto exclusivo de Disponibilidad e inventario; sin tablas compartidas con Reservas.
BEGIN;
CREATE SCHEMA IF NOT EXISTS hotels_meta;
REVOKE ALL ON SCHEMA hotels_meta FROM PUBLIC, anon, authenticated;
CREATE TABLE IF NOT EXISTS hotels_meta.service_owner(id INTEGER PRIMARY KEY CHECK(id=1),service TEXT NOT NULL);
INSERT INTO hotels_meta.service_owner VALUES (1,'availability') ON CONFLICT(id) DO NOTHING;
DO $$ BEGIN
  IF (SELECT service FROM hotels_meta.service_owner WHERE id=1) <> 'availability' THEN
    RAISE EXCEPTION 'La base pertenece a otro microservicio';
  END IF;
END $$;
ALTER TABLE hotels_meta.service_owner ENABLE ROW LEVEL SECURITY;
CREATE SCHEMA hotels_availability;
REVOKE ALL ON SCHEMA hotels_availability FROM PUBLIC, anon, authenticated;
CREATE TABLE hotels_availability.inventory(
  room_id TEXT PRIMARY KEY,total INTEGER NOT NULL CHECK(total>=1),
  sort_order INTEGER NOT NULL CHECK(sort_order>=0)
);
CREATE TABLE hotels_availability.allocations(
  reservation_id TEXT PRIMARY KEY,room_id TEXT NOT NULL DEFAULT '',
  checkin TEXT NOT NULL DEFAULT '',checkout TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL CHECK(status IN ('Asignada','Liberada')),
  CHECK(status='Liberada' OR (room_id<>'' AND checkin<>'' AND checkout>checkin))
);
CREATE INDEX allocation_dates ON hotels_availability.allocations(room_id,status,checkin,checkout);
ALTER TABLE hotels_availability.inventory ENABLE ROW LEVEL SECURITY;
ALTER TABLE hotels_availability.allocations ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON ALL TABLES IN SCHEMA hotels_availability FROM PUBLIC, anon, authenticated;
REVOKE ALL ON hotels_meta.service_owner FROM PUBLIC, anon, authenticated;
CREATE ROLE hotels_availability_app NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS CONNECTION LIMIT 10;
GRANT CONNECT ON DATABASE postgres TO hotels_availability_app;
GRANT USAGE ON SCHEMA hotels_availability,hotels_meta TO hotels_availability_app;
GRANT SELECT ON hotels_meta.service_owner TO hotels_availability_app;
GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA hotels_availability TO hotels_availability_app;
CREATE POLICY backend_owner_read ON hotels_meta.service_owner FOR SELECT TO hotels_availability_app USING(service='availability');
CREATE POLICY backend_service_access ON hotels_availability.inventory FOR ALL TO hotels_availability_app USING(true) WITH CHECK(true);
CREATE POLICY backend_service_access ON hotels_availability.allocations FOR ALL TO hotels_availability_app USING(true) WITH CHECK(true);
DO $$ BEGIN
  IF to_regprocedure('public.rls_auto_enable()') IS NOT NULL THEN
    REVOKE EXECUTE ON FUNCTION public.rls_auto_enable() FROM PUBLIC, anon, authenticated;
  END IF;
END $$;
COMMIT;
