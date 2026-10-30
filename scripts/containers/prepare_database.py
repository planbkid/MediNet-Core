"""Migraciones y permisos solo en la base local exclusiva; nunca desde la API."""
import os

from alembic import command
from alembic.config import Config
from psycopg import sql
from sqlalchemy import text

from app.admin_database import create_admin_engine


def main():
    expected = {'POSTGRES_DB': 'pac_local', 'POSTGRES_USER': 'pac_local_admin',
                'PAC_DB_USER': 'pac_local_api', 'DB_HOST': 'db', 'DB_PORT': '5432'}
    if any(os.environ.get(key) != value for key, value in expected.items()):
        raise RuntimeError('Destino distinto del entorno local exclusivo')
    engine = create_admin_engine()
    with engine.connect() as conn:
        if tuple(conn.execute(text('SELECT current_database(), current_user')).one()) != (
                'pac_local', 'pac_local_admin'):
            raise RuntimeError('Identidad administrativa incorrecta')
    config = Config('alembic.ini')
    with engine.connect() as conn:
        config.attributes['connection'] = conn
        command.upgrade(config, 'head')
    with engine.begin() as conn:
        exists = conn.scalar(text("SELECT EXISTS (SELECT FROM pg_roles WHERE rolname='pac_local_api')"))
        if not exists:
            conn.exec_driver_sql('CREATE ROLE pac_local_api LOGIN NOSUPERUSER NOCREATEDB '
                                 'NOCREATEROLE NOREPLICATION NOBYPASSRLS NOINHERIT')
            raw = conn.connection.driver_connection
            verifier = raw.pgconn.encrypt_password(os.environ['PAC_DB_PASSWORD'].encode(),
                                                   b'pac_local_api', b'scram-sha-256').decode()
            conn.exec_driver_sql(sql.SQL('ALTER ROLE pac_local_api PASSWORD {}').format(
                sql.Literal(verifier)).as_string())
        conn.exec_driver_sql('REVOKE TEMPORARY ON DATABASE pac_local FROM PUBLIC')
        conn.exec_driver_sql('GRANT CONNECT ON DATABASE pac_local TO pac_local_api')
        conn.exec_driver_sql('GRANT USAGE ON SCHEMA public TO pac_local_api')
        conn.exec_driver_sql('GRANT SELECT, INSERT, UPDATE ON public.patients TO pac_local_api')
        conn.exec_driver_sql('GRANT USAGE ON SEQUENCE public.patients_id_seq TO pac_local_api')
    engine.dispose()
    print('Migraciones y permisos locales preparados; sin mostrar credenciales.')


if __name__ == '__main__':
    # No imprimir excepciones SQL que puedan contener verificadores de contraseña.
    try:
        main()
    except Exception:
        raise SystemExit('Preparación administrativa fallida; revisar estado sin volcar secretos.') from None
