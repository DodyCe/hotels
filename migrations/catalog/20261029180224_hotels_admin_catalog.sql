BEGIN;
ALTER TABLE hotels_catalog.hotels ADD COLUMN active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1));
GRANT UPDATE ON hotels_catalog.hotels TO hotels_catalog_app;
COMMIT;
