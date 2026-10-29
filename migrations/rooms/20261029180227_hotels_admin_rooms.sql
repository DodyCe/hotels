BEGIN;
ALTER TABLE hotels_rooms.rooms ADD COLUMN active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1));
ALTER TABLE hotels_rooms.rooms ADD COLUMN inventory_ready INTEGER NOT NULL DEFAULT 1 CHECK(inventory_ready IN (0,1));
ALTER TABLE hotels_rooms.rooms ADD COLUMN initial_units INTEGER NOT NULL DEFAULT 1 CHECK(initial_units BETWEEN 1 AND 1000);
GRANT UPDATE ON hotels_rooms.rooms TO hotels_rooms_app;
COMMIT;
