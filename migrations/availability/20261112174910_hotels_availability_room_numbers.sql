BEGIN;
SET LOCAL lock_timeout = '5s';

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM hotels_meta.service_owner WHERE id = 1 AND service = 'availability') THEN
    RAISE EXCEPTION 'Esta migración pertenece a Disponibilidad e Inventario';
  END IF;
END $$;

CREATE TABLE hotels_availability.room_numbers (
  hotel_id TEXT NOT NULL,
  number TEXT NOT NULL CHECK (char_length(number) BETWEEN 1 AND 12 AND number ~ '^[A-Z0-9]+(-[A-Z0-9]+)*$'),
  room_id TEXT NOT NULL REFERENCES hotels_availability.inventory(room_id) ON DELETE CASCADE,
  PRIMARY KEY (hotel_id, number)
);

CREATE INDEX room_numbers_by_type ON hotels_availability.room_numbers(room_id);
ALTER TABLE hotels_availability.room_numbers ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON hotels_availability.room_numbers FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT, DELETE ON hotels_availability.room_numbers TO hotels_availability_app;
CREATE POLICY backend_room_numbers_read ON hotels_availability.room_numbers
  FOR SELECT TO hotels_availability_app USING (true);
CREATE POLICY backend_room_numbers_insert ON hotels_availability.room_numbers
  FOR INSERT TO hotels_availability_app WITH CHECK (true);
CREATE POLICY backend_room_numbers_delete ON hotels_availability.room_numbers
  FOR DELETE TO hotels_availability_app USING (true);

COMMIT;
