-- UPDATE requiere tanto el privilegio de tabla como su política RLS.
CREATE POLICY backend_catalog_update ON hotels_catalog.hotels
FOR UPDATE TO hotels_catalog_app USING (true) WITH CHECK (true);
