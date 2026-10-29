-- Estado de seguridad exclusivo de Autenticación. No se exponen enlaces al frontend.
BEGIN;
CREATE TABLE hotels_auth.login_security (
    email_hash TEXT PRIMARY KEY,
    failed_attempts INTEGER NOT NULL DEFAULT 0 CHECK(failed_attempts BETWEEN 0 AND 6),
    window_started DOUBLE PRECISION NOT NULL DEFAULT 0,
    locked_until DOUBLE PRECISION NOT NULL DEFAULT 0,
    reset_requested_at DOUBLE PRECISION NOT NULL DEFAULT 0
);
CREATE TABLE hotels_auth.password_resets (
    token_hash TEXT PRIMARY KEY,
    user_id TEXT NOT NULL UNIQUE REFERENCES hotels_auth.users(id) ON DELETE CASCADE,
    created DOUBLE PRECISION NOT NULL, expires DOUBLE PRECISION NOT NULL
);
ALTER TABLE hotels_auth.login_security ENABLE ROW LEVEL SECURITY;
ALTER TABLE hotels_auth.password_resets ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON hotels_auth.login_security,hotels_auth.password_resets FROM PUBLIC,anon,authenticated;
GRANT SELECT,INSERT,UPDATE,DELETE ON hotels_auth.login_security,hotels_auth.password_resets TO hotels_auth_app;
CREATE POLICY backend_auth_security_access ON hotels_auth.login_security
FOR ALL TO hotels_auth_app USING (true) WITH CHECK (true);
CREATE POLICY backend_auth_security_access ON hotels_auth.password_resets
FOR ALL TO hotels_auth_app USING (true) WITH CHECK (true);
COMMIT;
