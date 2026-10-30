"""Infraestructura exclusiva: migración/limpieza admin; solicitudes con rol limitado."""
import os
import sys

import pytest
from sqlalchemy import URL, create_engine, text

from tests.pac_test_support import ADMIN, API, DATABASE, PORT, guard_database, require

# Fallar antes de importar app o usar .env. Nombre y puerto no bastan: guard_database
# comprobará además contenedor, clúster y marcador exclusivo de esta ejecución.
require(os.environ.get('POSTGRES_DB') == DATABASE
        and os.environ.get('DB_HOST') == '127.0.0.1'
        and os.environ.get('DB_PORT') == str(PORT)
        and os.environ.get('POSTGRES_USER') == ADMIN
        and os.environ.get('PAC_DB_USER') == API
        and all(os.environ.get(k) for k in (
            'POSTGRES_PASSWORD', 'PAC_DB_PASSWORD', 'PAC_TEST_CONTAINER_ID',
            'PAC_TEST_SYSTEM_ID', 'PAC_TEST_MARKER')),
        'Ejecutar únicamente mediante .venv/bin/python scripts/run_pac_tests.py')
require('app.database' not in sys.modules, 'Configurar pruebas antes de importar app.database')

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from psycopg import sql

from app.database import engine
from app.main import app

admin_engine = create_engine(URL.create(
    'postgresql+psycopg', username=ADMIN, password=os.environ['POSTGRES_PASSWORD'],
    host='127.0.0.1', port=PORT, database=DATABASE,
), hide_parameters=True)


@pytest.fixture(scope='session', autouse=True)
def database():
    guard_database(admin_engine)
    config = Config('alembic.ini')
    with admin_engine.connect() as conn:
        config.attributes['connection'] = conn
        command.upgrade(config, 'head')
    guard_database(admin_engine)
    with admin_engine.begin() as conn:
        # SCRAM se calcula en el cliente: no se envía la contraseña en SQL.
        raw = conn.connection.driver_connection
        verifier = raw.pgconn.encrypt_password(
            os.environ['PAC_DB_PASSWORD'].encode(), API.encode(), b'scram-sha-256'
        ).decode()
        conn.exec_driver_sql(sql.SQL('''CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB
            NOCREATEROLE NOREPLICATION NOBYPASSRLS NOINHERIT PASSWORD {}''').format(
            sql.Identifier(API), sql.Literal(verifier)).as_string())
        conn.exec_driver_sql(f'REVOKE TEMPORARY ON DATABASE {DATABASE} FROM PUBLIC')
        conn.exec_driver_sql(f'GRANT CONNECT ON DATABASE {DATABASE} TO {API}')
        conn.exec_driver_sql(f'GRANT USAGE ON SCHEMA public TO {API}')
        conn.exec_driver_sql(f'GRANT SELECT, INSERT, UPDATE ON public.patients TO {API}')
        conn.exec_driver_sql(f'GRANT USAGE ON SEQUENCE public.patients_id_seq TO {API}')
    with engine.connect() as conn:
        identity = conn.execute(text('SELECT current_database(), current_user')).one()
        require(tuple(identity) == (DATABASE, API), 'La API no usa el rol limitado de pruebas')
    yield admin_engine
    engine.dispose()
    admin_engine.dispose()


@pytest.fixture(autouse=True)
def clean_test_data(database):
    guard_database(database)
    with database.begin() as conn:
        conn.execute(text('TRUNCATE patients RESTART IDENTITY'))
    yield


@pytest.fixture
def client():
    with TestClient(app) as client:
        yield client


@pytest.fixture
def payload():
    return {'run': '12.345.678-5', 'nombres': 'Ana María', 'apellido_paterno': 'Muñoz',
            'apellido_materno': "O'Neill", 'fecha_nacimiento': '1990-05-10',
            'prevision': 'FONASA', 'email': 'Ana.PAC@EXAMPLE.COM',
            'telefono': '+56 (9) 1234-5678', 'direccion': 'Calle Sintética 123'}
