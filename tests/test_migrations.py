import uuid

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, event, inspect, text

from app.database import engine
from app.services.patients import list_patients
from tests.pac_test_support import guard_database, mark_database


@pytest.fixture
def migration_db(database):
    # Solo el servidor temporal; cada caso usa una base NUEVA con nombre exclusivo.
    guard_database(database)
    name = 'pac_credentials_migration_' + uuid.uuid4().hex
    with database.connect().execution_options(isolation_level='AUTOCOMMIT') as connection:
        connection.exec_driver_sql(f'CREATE DATABASE "{name}"')
        mark_database(connection, name)
    isolated = create_engine(database.url.set(database=name), hide_parameters=True)
    guard_database(isolated, name)
    yield isolated
    isolated.dispose()


def upgrade(engine, target='head'):
    guard_database(engine, engine.url.database)
    config = Config('alembic.ini')
    with engine.connect() as connection:
        config.attributes['connection'] = connection
        command.upgrade(config, target)


def old_table(connection):
    # DDL del Paso 2, independiente del modelo ampliado y de la migración.
    connection.exec_driver_sql("""
        CREATE TABLE patients (
            id SERIAL PRIMARY KEY,
            run VARCHAR(10) NOT NULL UNIQUE,
            nombres VARCHAR(100) NOT NULL,
            apellido_paterno VARCHAR(60) NOT NULL,
            apellido_materno VARCHAR(60),
            fecha_nacimiento DATE NOT NULL,
            prevision VARCHAR(10) NOT NULL,
            email VARCHAR(254), telefono VARCHAR(15), direccion VARCHAR(200),
            created_at TIMESTAMPTZ DEFAULT now() NOT NULL,
            updated_at TIMESTAMPTZ DEFAULT now() NOT NULL,
            CONSTRAINT ck_patients_prevision CHECK (prevision IN ('FONASA','ISAPRE','CAPREDENA','DIPRECA')),
            CONSTRAINT ck_patients_run_formato CHECK (run ~ '^[0-9]{7,8}-[0-9K]$')
        )
    """)
    connection.exec_driver_sql('CREATE INDEX ix_patients_apellidos ON patients (apellido_paterno, apellido_materno)')


@pytest.mark.parametrize('legacy', [False, True])
def test_upgrade_empty_and_legacy_preserves_data(migration_db, legacy):
    before = None
    if legacy:
        with migration_db.begin() as connection:
            old_table(connection)
            connection.execute(text("""INSERT INTO patients
                (run,nombres,apellido_paterno,fecha_nacimiento,prevision)
                VALUES ('12345678-5','Sintético','Muñoz','1990-05-10','FONASA')"""))
            before = connection.execute(text('SELECT * FROM patients')).all()
    upgrade(migration_db)
    upgrade(migration_db)  # repetición idempotente
    info = inspect(migration_db)
    assert len(info.get_columns('patients')) == 12
    assert {'ix_patients_apellidos', 'ix_patients_paterno_prefix', 'ix_patients_materno_prefix'} <= {
        index['name'] for index in info.get_indexes('patients')}
    with migration_db.connect() as connection:
        assert connection.scalar(text('SELECT version_num FROM alembic_version')) == '0002'
        if before:
            assert connection.execute(text('SELECT * FROM patients')).all() == before
        else:
            assert connection.scalar(text('SELECT count(*) FROM patients')) == 0


def test_incompatible_schema_fails_without_changing_table(migration_db):
    with migration_db.begin() as conn:
        old_table(conn)
        conn.exec_driver_sql('ALTER TABLE patients ALTER COLUMN telefono TYPE VARCHAR(16)')
    with pytest.raises(RuntimeError, match='incompatible'):
        upgrade(migration_db)
    assert inspect(migration_db).get_columns('patients')[8]['type'].length == 16
    assert 'ix_patients_paterno_prefix' not in {i['name'] for i in inspect(migration_db).get_indexes('patients')}


def test_prefix_indexes_query_plan(database):
    from sqlalchemy.orm import Session
    # Volumen suficiente para que el optimizador pueda comparar alternativas.
    with database.begin() as connection:
        connection.execute(text("""INSERT INTO patients
            (run,nombres,apellido_paterno,apellido_materno,fecha_nacimiento,prevision)
            SELECT (20000000+n)::text || '-0', 'Sintético',
                CASE WHEN n <= 30 THEN 'Objetivo' || n ELSE 'Común' || n END,
                CASE WHEN n <= 30 THEN 'Selectivo' || n ELSE 'General' || n END,
                '1990-01-01'::date, 'FONASA'
            FROM generate_series(1,30000) AS n"""))
        connection.exec_driver_sql('ANALYZE patients')
    statements = []

    def capture(conn, cursor, statement, parameters, context, executemany):
        if statement.startswith('SELECT patients.id'):
            statements.append((statement, parameters))

    event.listen(engine, 'before_cursor_execute', capture)
    try:
        with Session(engine) as session:
            assert list_patients(session, apellido_paterno='OBJetivo')['total'] == 30
            assert list_patients(session, apellido_materno='SELectivo')['total'] == 30
    finally:
        event.remove(engine, 'before_cursor_execute', capture)
    assert len(statements) == 2
    for (statement, params), expected in zip(statements, ['ix_patients_paterno_prefix', 'ix_patients_materno_prefix']):
        with database.connect() as connection:
            plan = connection.exec_driver_sql('EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) ' + statement, params).scalar_one()
        assert expected in str(plan)
        print(f"EXPLAIN: {expected}; 30000 filas; "
              f"planificación={plan[0]['Planning Time']} ms; "
              f"ejecución={plan[0]['Execution Time']} ms; "
              f"bloques compartidos hit={plan[0]['Plan']['Shared Hit Blocks']}")
