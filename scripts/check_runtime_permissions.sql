-- Solo metadatos. Ejecutar conectado como el usuario limitado, no administrador.
BEGIN READ ONLY;
SELECT current_database(), current_user;
SELECT rolcanlogin, rolsuper, rolcreatedb, rolcreaterole,
       rolreplication, rolbypassrls, rolinherit
FROM pg_roles WHERE rolname = current_user;

SELECT roleid::regrole AS membership
FROM pg_auth_members
WHERE member = (SELECT oid FROM pg_roles WHERE rolname = current_user);

SELECT p AS privilege, has_database_privilege(current_user, current_database(), p) AS allowed
FROM unnest(ARRAY['CONNECT','CREATE','TEMPORARY']) AS p;
SELECT p AS privilege, has_schema_privilege(current_user, 'public', p) AS allowed
FROM unnest(ARRAY['USAGE','CREATE']) AS p;
SELECT p AS privilege, has_table_privilege(current_user, 'public.patients', p) AS allowed
FROM unnest(ARRAY['SELECT','INSERT','UPDATE','DELETE','TRUNCATE',
                  'REFERENCES','TRIGGER','MAINTAIN']) AS p;
SELECT p AS privilege, has_any_column_privilege(current_user, 'public.patients', p) AS allowed
FROM unnest(ARRAY['SELECT','INSERT','UPDATE','REFERENCES']) AS p;
SELECT p AS privilege, has_sequence_privilege(current_user, 'public.patients_id_seq', p) AS allowed
FROM unnest(ARRAY['USAGE','SELECT','UPDATE']) AS p;
SELECT p AS privilege, has_table_privilege(current_user, 'public.alembic_version', p) AS allowed
FROM unnest(ARRAY['SELECT','INSERT','UPDATE','DELETE','TRUNCATE']) AS p;

SELECT relname, pg_get_userbyid(relowner) AS owner, relacl
FROM pg_class WHERE oid IN ('public.patients'::regclass,
                           'public.patients_id_seq'::regclass,
                           'public.alembic_version'::regclass);
SELECT nspname, pg_get_userbyid(nspowner) AS owner, nspacl
FROM pg_namespace WHERE nspname = 'public';
SELECT datname, pg_get_userbyid(datdba) AS owner, datacl
FROM pg_database WHERE datname = current_database();
ROLLBACK;
