# 3. Modelo de datos por servicio

Cada microservicio tiene **su propia base PostgreSQL** en un proyecto Supabase distinto. Ningún servicio lee tablas de otro. Las referencias entre dominios (por ejemplo, `user_id` en Reservas) son identificadores de texto que se resuelven por API, sin claves foráneas entre bases.

Las tablas viven en un esquema privado por servicio (`hotels_auth`, `hotels_catalog`, etc.), con RLS activo y un rol técnico propio. Las migraciones SQL están en `migrations/<servicio>/`. En local, si la URL de una base está vacía, el servicio crea las mismas tablas en SQLite.

Cada base tiene además `hotels_meta.service_owner`, una fila que indica a qué servicio pertenece. Si se apunta un servicio a la base de otro, la inicialización falla.

## 3.1 Autenticación (`hotels_auth`)

```mermaid
erDiagram
  users ||--o{ sessions : "abre"
  users ||--o| guests : "tiene perfil"
  users ||--o| password_resets : "pide recuperación"
  users {
    text id PK
    text name
    text email UK
    text salt
    text password_hash
    text role "guest o admin"
    int active "1 o 0"
    double created
  }
  sessions {
    text token_hash PK "SHA-256 del token"
    text user_id FK
    double expires
  }
  guests {
    text id PK
    text user_id FK, UK "puede ser nulo"
    text name
    text email UK
    text phone
    int active
    double created
  }
  password_resets {
    text token_hash PK
    text user_id FK, UK
    double created
    double expires
  }
  login_security {
    text email_hash PK "SHA-256 del correo"
    int failed_attempts "0 a 6"
    double window_started
    double locked_until
    double reset_requested_at
  }
  outbox {
    text id PK
    text body "evento JSON"
    int attempts
    double next_try
    int delivered
  }
```

- **users:** credenciales. La contraseña se guarda como scrypt con sal propia, nunca en texto.
- **sessions:** solo se guarda el hash del token; la cookie lleva el token. Duran ocho horas.
- **guests:** perfil del huésped que gestiona el administrador. Puede existir sin cuenta.
- **login_security:** contador de intentos fallidos por correo, para el bloqueo temporal.
- **password_resets:** un token vigente por usuario, válido 15 minutos.
- **outbox:** eventos pendientes de entregar a Notificaciones.

## 3.2 Notificaciones (`hotels_notifications`)

```mermaid
erDiagram
  messages {
    text id PK "id del evento, evita duplicados"
    text user_id "referencia lógica a Auth"
    text recipient
    text subject
    text body
    text status
    double created
    int attempts
    double next_try
  }
```

- El `id` es el identificador del evento. Si el mismo evento llega dos veces, no se crea otro mensaje.
- `status` toma: `vista_previa`, `pendiente`, `reintentando`, `aceptado_smtp`, `aceptado_api`, `error` y `caducado` (enlace de recuperación vencido antes de enviarse).

## 3.3 Reservas (`hotels_reservations`)

```mermaid
erDiagram
  reservations {
    text id PK "HT-..."
    text user_id "referencia lógica a Auth"
    text hotel_id "referencia lógica a Catálogo"
    text room_id "referencia lógica a Habitaciones"
    text hotel_name "copia histórica"
    text room_name "copia histórica"
    text checkin "AAAA-MM-DD"
    text checkout
    int guests "1 a 20"
    bigint total "calculado por el servidor"
    text status
    int inventory_synced
    double created
  }
  outbox {
    text id PK
    text body
    int attempts
    double next_try
    int delivered
  }
```

- `status` solo admite `Pendiente`, `Confirmada`, `Cancelando`, `Cancelada` y `Rechazada`.
- Se guardan nombre del hotel, nombre de la habitación y total como copia. Si el catálogo cambia después, la reserva conserva lo que el huésped contrató.
- `inventory_synced` indica si Inventario ya confirmó la asignación o la liberación.

## 3.4 Catálogo de hoteles (`hotels_catalog`)

```mermaid
erDiagram
  hotels {
    text id PK
    text document "JSON del hotel"
    int sort_order
    int active
  }
```

`document` es un JSON validado por el servicio con: `id`, `name`, `city`, `area`, `address`, `description`, `badge`, `tags`, `amenities`, `image`, `photographer`, `photoPage` y `source`. Se eligió un documento porque los hoteles tienen listas (servicios, comodidades) que no se consultan por separado. Una restricción de la base exige que el `id` del JSON coincida con el de la fila.

## 3.5 Habitaciones (`hotels_rooms`)

```mermaid
erDiagram
  rooms {
    text id PK
    text hotelId "referencia lógica a Catálogo"
    text name
    int capacity "1 a 20"
    bigint price "tarifa por noche en COP"
    int sort_order
    int active
    int inventory_ready "1 cuando Inventario creó las unidades"
    int initial_units "unidades pedidas al crear"
  }
```

Índice por `hotelId` y `capacity` para el filtro de búsqueda.

## 3.6 Disponibilidad e inventario (`hotels_availability`)

```mermaid
erDiagram
  inventory ||--o{ allocations : "room_id"
  inventory {
    text room_id PK "referencia lógica a Habitaciones"
    int total "unidades, mínimo 1"
    int sort_order
  }
  allocations {
    text reservation_id PK "referencia lógica a Reservas"
    text room_id
    text checkin
    text checkout
    text status "Asignada o Liberada"
  }
```

- Una unidad está ocupada en una noche si existe una asignación `Asignada` que cubre esa noche. La fecha de salida no ocupa noche.
- Índice por `room_id`, `status`, `checkin` y `checkout` para calcular la disponibilidad en una sola consulta.
- Una asignación `Liberada` no se puede volver a asignar; así una petición tardía no reactiva una reserva cancelada.

## 3.7 Referencias entre dominios

```mermaid
flowchart LR
  U["Auth.users.id"] -.-> RU["Reservas.user_id"]
  U -.-> NU["Notificaciones.user_id"]
  H["Catálogo.hotels.id"] -.-> RH["Habitaciones.hotelId"]
  H -.-> RSH["Reservas.hotel_id"]
  R["Habitaciones.rooms.id"] -.-> IR["Inventario.room_id"]
  R -.-> RSR["Reservas.room_id"]
  RS["Reservas.id"] -.-> IA["Inventario.allocations.reservation_id"]
```

Las líneas punteadas son referencias lógicas. Las valida el servicio por API en el momento de crear el registro: Habitaciones consulta Catálogo antes de crear un tipo, y Reservas consulta Habitaciones y Catálogo antes de reservar.

## 3.8 Datos iniciales

`seed/hotels.json`, `seed/rooms.json` y `seed/inventory.json` cargan tres hoteles de referencia en Montería, seis tipos de habitación (dos por hotel) y una unidad por tipo. Cada archivo inicializa solo su servicio y no sobrescribe registros existentes.
