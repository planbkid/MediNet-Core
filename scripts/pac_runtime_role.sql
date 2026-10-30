-- Aplicación MANUAL pendiente. No ejecutar desde migraciones ni desde la API.
-- Conectar como medinet_pac a medinet_pac y usar psql con ON_ERROR_STOP.
BEGIN;
DO $$
BEGIN
    IF current_database() <> 'medinet_pac' OR current_user <> 'medinet_pac' THEN
        RAISE EXCEPTION 'Conexión administrativa de desarrollo incorrecta';
    END IF;
END $$;

-- El administrador conserva propiedades y privilegios. Sin membresías nuevas.
CREATE ROLE medinet_pac_api LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE
    NOREPLICATION NOBYPASSRLS NOINHERIT PASSWORD NULL;

-- Afecta a quienes obtengan TEMPORARY mediante PUBLIC en esta base.
REVOKE TEMPORARY ON DATABASE medinet_pac FROM PUBLIC;
GRANT CONNECT ON DATABASE medinet_pac TO medinet_pac_api;
GRANT USAGE ON SCHEMA public TO medinet_pac_api;
GRANT SELECT, INSERT, UPDATE ON public.patients TO medinet_pac_api;
-- USAGE permite nextval(); no concede setval().
GRANT USAGE ON SEQUENCE public.patients_id_seq TO medinet_pac_api;
COMMIT;

-- Después, en psql interactivo: \password medinet_pac_api
-- No introducir contraseñas en este archivo ni en ALTER ROLE literal.
