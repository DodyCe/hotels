-- Solo el backend de Habitaciones puede editar sus propios registros.
CREATE POLICY backend_rooms_update ON hotels_rooms.rooms
FOR UPDATE TO hotels_rooms_app USING (true) WITH CHECK (true);
