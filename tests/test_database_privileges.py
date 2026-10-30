"""Permisos y operaciones reales: únicamente en el servidor exclusivo del runner."""
import os
from pathlib import Path
import subprocess
import sys

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.exc import DBAPIError, OperationalError
from sqlalchemy.orm import Session

from app.database import engine
from app.models import Patient
from tests.pac_test_support import ADMIN, API, DATABASE, guard_database


def test_effective_privileges(database):
    with engine.connect() as conn:
        assert conn.scalar(text('SELECT current_user')) == API
        role = conn.execute(text('''SELECT rolcanlogin,rolsuper,rolcreatedb,rolcreaterole,
            rolreplication,rolbypassrls,rolinherit FROM pg_roles WHERE rolname=current_user''')).one()
        assert tuple(role) == (True, False, False, False, False, False, False)
        assert conn.scalar(text('''SELECT count(*) FROM pg_auth_members
            WHERE member=(SELECT oid FROM pg_roles WHERE rolname=current_user)''')) == 0
        for privilege, expected in [('CONNECT', True), ('CREATE', False), ('TEMPORARY', False)]:
            assert conn.scalar(text('SELECT has_database_privilege(current_user,:db,:p)'),
                               {'db': DATABASE, 'p': privilege}) is expected
        for privilege, expected in [('USAGE', True), ('CREATE', False)]:
            assert conn.scalar(text("SELECT has_schema_privilege(current_user,'public',:p)"),
                               {'p': privilege}) is expected
        for privilege in ['SELECT', 'INSERT', 'UPDATE', 'DELETE', 'TRUNCATE',
                          'REFERENCES', 'TRIGGER', 'MAINTAIN']:
            assert conn.scalar(text("SELECT has_table_privilege(current_user,'public.patients',:p)"),
                               {'p': privilege}) is (privilege in {'SELECT', 'INSERT', 'UPDATE'})
        for privilege in ['USAGE', 'SELECT', 'UPDATE']:
            assert conn.scalar(text("SELECT has_sequence_privilege(current_user,'public.patients_id_seq',:p)"),
                               {'p': privilege}) is (privilege == 'USAGE')
        assert not conn.scalar(text("SELECT has_table_privilege(current_user,'public.alembic_version','SELECT')"))
    with database.connect() as conn:
        assert conn.scalar(text("SELECT pg_get_userbyid(relowner) FROM pg_class WHERE oid='public.patients'::regclass")) == ADMIN
        assert conn.scalar(text('''SELECT count(*) FROM pg_database d,
            LATERAL aclexplode(coalesce(d.datacl,acldefault('d',d.datdba))) a
            WHERE d.datname=current_database() AND a.grantee=0
            AND a.privilege_type='TEMPORARY' ''')) == 0
        assert conn.scalar(text('''SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace,
            LATERAL aclexplode(c.relacl) a WHERE n.nspname='public' AND a.grantee=0''')) == 0


@pytest.mark.parametrize('statement', [
    'DELETE FROM public.patients',
    'TRUNCATE public.patients',
    'CREATE TABLE public.forbidden_table (id integer)',
    'CREATE TEMP TABLE forbidden_temp (id integer)',
    'CREATE SCHEMA forbidden_schema',
    'ALTER TABLE public.patients ADD COLUMN forbidden_column integer',
    "SELECT setval('public.patients_id_seq', 100)",
    'CREATE ROLE forbidden_role',
    f'ALTER ROLE {API} SUPERUSER',
    f'SET ROLE {ADMIN}',
    'SELECT * FROM public.alembic_version',
    "UPDATE public.alembic_version SET version_num='forbidden'",
])
def test_forbidden_operations_rejected(database, statement):
    guard_database(database)
    with engine.connect() as conn:
        transaction = conn.begin()
        try:
            with pytest.raises(DBAPIError) as error:
                conn.exec_driver_sql(statement)
            assert error.value.orig.sqlstate == '42501'
        finally:
            # Incluso un permiso concedido por error queda contenido en la base aislada.
            transaction.rollback()
        assert conn.scalar(text('SELECT current_user')) == API


def test_requests_use_limited_user_and_persist_in_new_session(client, payload):
    identities = []

    def capture(conn, cursor, statement, parameters, context, executemany):
        if 'patients' in statement.lower():
            cursor.execute('SELECT current_user')
            identities.append(cursor.fetchone()[0])

    event.listen(engine, 'before_cursor_execute', capture)
    try:
        response = client.post('/patients', json=payload)
        assert response.status_code == 201
        identifier = response.json()['id']
        # Nueva sesión SQLAlchemy: evidencia independiente de persistencia.
        with Session(engine) as session:
            assert session.get(Patient, identifier).run == '12345678-5'
        assert client.get(f'/patients/{identifier}').status_code == 200
        assert client.get('/patients').json()['total'] == 1
        assert client.patch(f'/patients/{identifier}', json={'email': None}).status_code == 200
    finally:
        event.remove(engine, 'before_cursor_execute', capture)
    assert identities and set(identities) == {API}
    print(f'Identidad SQL de POST/GET/PATCH: {API}; persistencia en sesión nueva: OK')


def test_password_is_actually_required():
    wrong = create_engine(engine.url.set(password='deliberately-wrong-test-only'), hide_parameters=True)
    try:
        with pytest.raises(OperationalError):
            with wrong.connect():
                pass
    finally:
        wrong.dispose()


def test_models_and_creation_command_import_without_credentials():
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(('POSTGRES_', 'PAC_DB_', 'DB_'))}
    result = subprocess.run([sys.executable, '-c',
        "import sys; import app.models; import app.crear_tablas; "
        "assert 'app.database' not in sys.modules; "
        "assert 'app.admin_database' not in sys.modules"], env=env, capture_output=True)
    assert result.returncode == 0
    # Tener .env en disco no habilita fallback administrativo en la API.
    result = subprocess.run([sys.executable, '-c', 'import app.database'], env=env, capture_output=True)
    assert result.returncode != 0 and b'PAC_DB_USER' in result.stderr


def test_alembic_cannot_use_api_connection(database):
    from alembic import command
    from alembic.config import Config
    guard_database(database)
    with engine.connect() as conn:
        config = Config('alembic.ini')
        config.attributes['connection'] = conn
        with pytest.raises(DBAPIError) as error:
            command.upgrade(config, 'head')
        assert error.value.orig.sqlstate == '42501'


def test_admin_settings_do_not_read_development_env(monkeypatch):
    from app import admin_database
    monkeypatch.setattr(admin_database, 'dotenv_values',
                        lambda *a: pytest.fail('No leer .env de desarrollo en pruebas'))
    admin = admin_database.create_admin_engine()
    try:
        assert admin.url.username == ADMIN
        assert admin.url.database == DATABASE
    finally:
        admin.dispose()


def test_read_only_permissions_script():
    script = Path('scripts/check_runtime_permissions.sql').read_text()
    with engine.connect() as conn:
        with conn.connection.driver_connection.cursor() as cursor:
            cursor.execute(script)
            identities = []
            while True:
                if cursor.description:
                    rows = cursor.fetchall()
                    if [c.name for c in cursor.description] == ['current_database', 'current_user']:
                        identities.extend(rows)
                if not cursor.nextset():
                    break
    assert identities == [(DATABASE, API)]


def test_guard_rejects_development_and_wrong_marker(database, monkeypatch):
    wrong = create_engine(database.url.set(database='medinet_pac', port=5433), hide_parameters=True)
    try:
        with pytest.raises(RuntimeError, match='fuera del entorno'):
            guard_database(wrong)
    finally:
        wrong.dispose()
    monkeypatch.setenv('PAC_TEST_MARKER', 'wrong-marker')
    with pytest.raises(RuntimeError, match='no pertenece'):
        guard_database(database)
