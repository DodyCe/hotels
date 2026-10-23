-- Aplicar únicamente en el proyecto de Catálogo. La contraseña se aprovisiona aparte.
BEGIN;
CREATE SCHEMA IF NOT EXISTS hotels_meta;
REVOKE ALL ON SCHEMA hotels_meta FROM PUBLIC, anon, authenticated;
CREATE TABLE IF NOT EXISTS hotels_meta.service_owner(id INTEGER PRIMARY KEY CHECK(id=1), service TEXT NOT NULL);
INSERT INTO hotels_meta.service_owner VALUES (1,'catalog') ON CONFLICT(id) DO NOTHING;
DO $$ BEGIN
  IF (SELECT service FROM hotels_meta.service_owner WHERE id=1) <> 'catalog' THEN
    RAISE EXCEPTION 'La base pertenece a otro microservicio';
  END IF;
END $$;
ALTER TABLE hotels_meta.service_owner ENABLE ROW LEVEL SECURITY;
CREATE SCHEMA hotels_catalog;
REVOKE ALL ON SCHEMA hotels_catalog FROM PUBLIC, anon, authenticated;
CREATE TABLE hotels_catalog.hotels(
  id TEXT PRIMARY KEY,
  document TEXT NOT NULL CHECK(jsonb_typeof(document::jsonb)='object' AND document::jsonb->>'id'=id),
  sort_order INTEGER NOT NULL CHECK(sort_order>=0)
);
ALTER TABLE hotels_catalog.hotels ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON ALL TABLES IN SCHEMA hotels_catalog FROM PUBLIC, anon, authenticated;
REVOKE ALL ON hotels_meta.service_owner FROM PUBLIC, anon, authenticated;
CREATE ROLE hotels_catalog_app NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS CONNECTION LIMIT 10;
GRANT CONNECT ON DATABASE postgres TO hotels_catalog_app;
GRANT USAGE ON SCHEMA hotels_catalog,hotels_meta TO hotels_catalog_app;
GRANT SELECT ON hotels_meta.service_owner TO hotels_catalog_app;
-- SELECT para las APIs e INSERT para la migración inicial; sin UPDATE, DELETE ni DDL.
GRANT SELECT,INSERT ON hotels_catalog.hotels TO hotels_catalog_app;
CREATE POLICY backend_owner_read ON hotels_meta.service_owner FOR SELECT TO hotels_catalog_app USING(service='catalog');
CREATE POLICY backend_catalog_read ON hotels_catalog.hotels FOR SELECT TO hotels_catalog_app USING(true);
CREATE POLICY backend_catalog_seed ON hotels_catalog.hotels FOR INSERT TO hotels_catalog_app WITH CHECK(true);
-- El asistente de RLS del panel crea una función administrativa; no se publica su ejecución.
DO $$ BEGIN
  IF to_regprocedure('public.rls_auto_enable()') IS NOT NULL THEN
    REVOKE EXECUTE ON FUNCTION public.rls_auto_enable() FROM PUBLIC, anon, authenticated;
  END IF;
END $$;
COMMIT;
