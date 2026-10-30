from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from threading import Barrier

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import engine
from app.main import app
from app.models import Patient
from app.schemas import PatientCreate
from app.services.patients import commit_patient, create_patient
from app.validators.run import normalize_run


@pytest.mark.parametrize(('value', 'expected'), [
    ('12345678-5', '12345678-5'), ('12.345.678-5', '12345678-5'),
    ('123456785', '12345678-5'), ('12.345.6785', '12345678-5'),
    ('1.000.005-k', '1000005-K'), ('1000005K', '1000005-K'),
    ('1.000.013-0', '1000013-0'),
])
def test_run_vectors(value, expected):
    assert normalize_run(value) == expected


@pytest.mark.parametrize('value', [
    '', '12345678-4', '123A5678-5', '00000000-0', '01234567-4',
    '0000000-0', '123456-0', '123456789-0', '12 345 678-5',
    '12..345.678-5', '+12345678-5', '１２３４５６７８-5', '12345678-5<script>',
])
def test_run_invalid(value):
    with pytest.raises(ValueError):
        normalize_run(value)


def test_health_docs_and_contract(client):
    assert client.get('/health').json() == {'status': 'ok'}
    assert client.get('/docs').status_code == 200
    schema = client.get('/openapi.json').json()
    assert set(schema['paths']['/patients']) == {'get', 'post'}
    assert set(schema['paths']['/patients/{patient_id}']) == {'get', 'patch'}
    assert 'post' in schema['paths']['/patients/validate-run']
    assert schema['components']['schemas']['PatientCreate']['additionalProperties'] is False


def test_create_duplicate_and_recovery(client, payload):
    response = client.post('/patients', json=payload)
    assert response.status_code == 201
    patient = response.json()
    assert response.headers['location'].endswith(f"/patients/{patient['id']}")
    assert patient['run'] == '12345678-5'
    assert patient['email'] == 'Ana.PAC@example.com'
    assert patient['telefono'] == '56912345678'
    assert patient['created_at'] and patient['updated_at']
    assert client.get(f"/patients/{patient['id']}").json() == patient
    assert client.post('/patients', json=payload | {'run': '123456785'}).status_code == 409
    assert client.get('/patients').json()['total'] == 1
    assert client.post('/patients', json=payload | {'run': '1000005-K'}).status_code == 201


def test_concurrent_duplicate(client, payload, monkeypatch):
    # Sincronizar ambos flush: fuerza que las dos solicitudes lleguen a la UNIQUE.
    from app.services import patients
    original = patients.commit_patient
    barrier = Barrier(2)

    def simultaneous(db, patient):
        barrier.wait(timeout=10)
        return original(db, patient)

    monkeypatch.setattr(patients, 'commit_patient', simultaneous)

    def post(run):
        with TestClient(app) as thread_client:
            return thread_client.post('/patients', json=payload | {'run': run}).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(pool.map(post, ['12.345.678-5', '123456785']))
    assert sorted(statuses) == [201, 409]
    assert client.get('/patients').json()['total'] == 1


@pytest.mark.parametrize('changes', [
    {'run': '12345678-4'}, {'run': '\n12345678-5'}, {'prevision': 'OTRA'},
    {'fecha_nacimiento': (date.today() + timedelta(days=1)).isoformat()},
    {'fecha_nacimiento': '2000-02-30'}, {'nombres': 'A' * 101},
    {'apellido_paterno': 'A' * 61}, {'apellido_materno': 'A' * 61},
    {'direccion': 'A' * 201}, {'telefono': '1' * 16}, {'telefono': 'abc'},
    {'email': 'sin-arroba'}, {'email': 'x' * 245 + '@example.com'},
    {'nombres': '  '}, {'apellido_paterno': 'A\x00B'},
    {'nombres': 'Ana\nMaría'}, {'nombres': None}, {'id': 12},
    {'created_at': '2000-01-01'}, {'campo_extra': 'x'}, {'run': 123456785},
])
def test_fields_invalid(client, payload, changes):
    response = client.post('/patients', json=payload | changes)
    assert response.status_code == 422
    assert 'input' not in response.text and 'INSERT INTO' not in response.text


def test_unicode_prevision_and_limits(client, payload):
    response = client.post('/patients', json=payload | {
        'nombres': '  Jose\u0301   María-Ñancu  ', 'apellido_paterno': " O'Neill ",
        'prevision': ' isapre ', 'telefono': '1' * 15, 'direccion': 'A' * 200,
        'apellido_materno': 'A' * 60,
    })
    assert response.status_code == 201
    assert response.json()['nombres'] == 'José María-Ñancu'
    assert response.json()['apellido_paterno'] == "O'Neill"
    assert response.json()['prevision'] == 'ISAPRE'


@pytest.mark.parametrize('value, expected', [
    ('12.345.678-5', {'valid': True, 'normalized_run': '12345678-5'}),
    ('12345678-4', {'valid': False, 'normalized_run': None}),
    ('', {'valid': False, 'normalized_run': None}),
])
def test_validate_run(client, value, expected):
    response = client.post('/patients/validate-run', json={'run': value})
    assert response.status_code == 200 and response.json() == expected
    assert client.get('/patients').json()['total'] == 0


@pytest.mark.parametrize('value', [{}, {'run': None}, {'run': 123}, {'run': '12345678-5', 'extra': 1}, []])
def test_validate_run_bad_body(client, value):
    assert client.post('/patients/validate-run', json=value).status_code == 422


def test_patch_preserves_and_clears(client, payload):
    patient = client.post('/patients', json=payload).json()
    path = f"/patients/{patient['id']}"
    updated = client.patch(path, json={'telefono': '987654321'}).json()
    assert updated['telefono'] == '987654321'
    assert updated['updated_at'] >= patient['updated_at']
    for key in set(payload) - {'telefono', 'run', 'email'}:
        assert updated[key] == patient[key]
    assert client.patch(path, json={'email': None, 'apellido_materno': None}).json()['email'] is None
    assert client.get(path).json()['apellido_materno'] is None
    assert client.patch(path, json={'run': '1.000.005-k'}).json()['run'] == '1000005-K'


@pytest.mark.parametrize('changes', [{}, {'run': None}, {'nombres': None},
    {'apellido_paterno': None}, {'fecha_nacimiento': None}, {'prevision': None},
    {'run': '12345678-4'}, {'id': 7}, {'updated_at': '2000-01-01'},
    {'fecha_nacimiento': '2999-01-01'}, {'telefono': 'x'}])
def test_patch_invalid(client, payload, changes):
    patient = client.post('/patients', json=payload).json()
    assert client.patch(f"/patients/{patient['id']}", json=changes).status_code == 422


def test_patch_duplicate_and_missing(client, payload):
    patient = client.post('/patients', json=payload).json()
    other = client.post('/patients', json=payload | {'run': '1000005-K'}).json()
    assert client.patch(f"/patients/{other['id']}", json={'run': patient['run']}).status_code == 409
    assert client.patch(f"/patients/{other['id']}", json={'prevision': 'DIPRECA'}).status_code == 200
    assert client.get('/patients/99999').status_code == 404
    assert client.patch('/patients/99999', json={'telefono': None}).status_code == 404


@pytest.mark.parametrize('patient_id', ['0', '-1', 'abc', '1.5'])
def test_invalid_ids(client, patient_id):
    assert client.get(f'/patients/{patient_id}').status_code == 422
    assert client.patch(f'/patients/{patient_id}', json={'email': None}).status_code == 422


def test_search_combined_pagination_and_literals(client, payload):
    rows = [
        ('12345678-5', 'Muñoz', 'Soto', 'FONASA'),
        ('1000005-K', 'Muñoz', 'Soto', 'ISAPRE'),
        ('1000013-0', 'Muñoz', None, 'FONASA'),
        ('1000019-K', '%_\\Literal', 'Soto', 'FONASA'),
    ]
    for run, paterno, materno, prevision in rows:
        assert client.post('/patients', json=payload | {
            'run': run, 'apellido_paterno': paterno, 'apellido_materno': materno,
            'prevision': prevision}).status_code == 201
    response = client.get('/patients', params={
        'apellido_paterno': 'mUÑ', 'apellido_materno': 'so', 'prevision': ' fonasa ',
    }).json()
    assert response['total'] == 1 and response['items'][0]['run'] == '12345678-5'
    assert client.get('/patients', params={'run': '12.345.678-5'}).json()['total'] == 1
    assert client.get('/patients', params={'apellido_paterno': 'Munoz'}).json()['items'] == []
    for prefix in ['%', '%_', '%_\\']:
        result = client.get('/patients', params={'apellido_paterno': prefix}).json()
        assert result['total'] == 1 and result['items'][0]['run'] == '1000019-K'
    first = client.get('/patients', params={'page_size': 2}).json()
    second = client.get('/patients', params={'page': 2, 'page_size': 2}).json()
    assert first['total'] == second['total'] == 4
    assert first['page'] == 1 and first['page_size'] == 2
    assert [p['run'] for p in first['items'] + second['items']] == [
        '1000019-K', '12345678-5', '1000005-K', '1000013-0']
    assert client.get('/patients', params={'page': 100}).json()['items'] == []


@pytest.mark.parametrize('params', [{'page': 0}, {'page': -1}, {'page': '1.5'},
    {'page': 100001}, {'page': 9223372036854775808}, {'page': '9' * 1000},
    {'page_size': 0}, {'page_size': 101},
    {'page': 'x'}, {'run': 'invalid'}, {'prevision': 'OTRA'}, {'apellido_paterno': ''}])
def test_bad_filters(client, params, monkeypatch):
    from app.services import patients

    def unexpected_query(*args, **kwargs):
        pytest.fail('Una entrada inválida no debe ejecutar el listado')

    monkeypatch.setattr(patients, 'list_patients', unexpected_query)
    assert client.get('/patients', params=params).status_code == 422


@pytest.mark.parametrize('page', [1, 100000])
@pytest.mark.parametrize('page_size', [1, 100])
def test_pagination_limits_and_empty_database(client, page, page_size):
    response = client.get('/patients', params={'page': page, 'page_size': page_size})
    assert response.status_code == 200
    assert response.json() == {
        'items': [], 'total': 0, 'page': page, 'page_size': page_size,
    }


def test_pagination_beyond_results_and_defaults(client, payload):
    created = client.post('/patients', json=payload)
    assert created.status_code == 201
    response = client.get('/patients')
    assert response.status_code == 200
    assert response.json() == {
        'items': [created.json()], 'total': 1, 'page': 1, 'page_size': 20,
    }
    for page in (2, 100000):
        response = client.get('/patients', params={'page': page, 'page_size': 100})
        assert response.status_code == 200
        assert response.json() == {
            'items': [], 'total': 1, 'page': page, 'page_size': 100,
        }


def test_pagination_openapi_limits(client):
    schema = client.get('/openapi.json').json()
    parameters = {p['name']: p['schema']
                  for p in schema['paths']['/patients']['get']['parameters']}
    assert parameters['page']['minimum'] == 1
    assert parameters['page']['maximum'] == 100000
    assert parameters['page']['default'] == 1


def test_sqli_and_xss_json(client, payload):
    attack = "' OR 1=1 --"
    tag = '<script>alert(1)</script>'
    response = client.post('/patients', json=payload | {'apellido_paterno': attack, 'direccion': tag})
    assert response.status_code == 201
    assert response.headers['content-type'] == 'application/json'
    assert response.json()['direccion'] == tag
    assert client.get('/patients', params={'apellido_paterno': attack}).json()['total'] == 1
    assert client.get('/patients', params={'apellido_paterno': "x' OR 1=1 --"}).json()['total'] == 0
    assert client.get('/patients', params={'run': attack}).status_code == 422
    assert client.post('/patients', json=payload | {'run': attack}).status_code == 422
    assert client.get('/patients').json()['total'] == 1


def test_same_session_rollback_and_other_integrity(payload):
    data = PatientCreate.model_validate(payload)
    with Session(engine) as db:
        create_patient(db, data)
        with pytest.raises(HTTPException) as duplicate:
            create_patient(db, data)
        assert duplicate.value.status_code == 409
        assert create_patient(db, PatientCreate.model_validate(payload | {'run': '1000005-K'})).id
        bad = Patient(**(data.model_dump() | {'run': '1000013-0', 'prevision': 'OTRA'}))
        db.add(bad)
        with pytest.raises(HTTPException) as integrity:
            commit_patient(db, bad)
        assert integrity.value.status_code == 500
        assert db.scalar(select(func.count()).select_from(Patient)) == 2


def test_dependency_closes_session(client, monkeypatch):
    from app import database
    sessions = []

    class TrackingSession(Session):
        closed = False

        def close(self):
            self.closed = True
            super().close()

    def factory():
        session = TrackingSession(engine)
        sessions.append(session)
        return session

    monkeypatch.setattr(database, 'SessionLocal', factory)
    assert client.get('/patients').status_code == 200
    assert client.get('/patients/9999').status_code == 404
    assert all(s.closed for s in sessions) and len(sessions) == 2


def test_unavailable_database_is_sanitized(client, monkeypatch):
    from app import database
    from sqlalchemy.exc import OperationalError

    def failing_session():
        raise OperationalError('SELECT sensitive', {'secret': 'do-not-return'}, Exception('private'))

    monkeypatch.setattr(database, 'SessionLocal', failing_session)
    response = client.get('/patients')
    assert response.status_code == 503
    assert response.json() == {'detail': 'Base de datos no disponible'}


def test_legacy_creation_command_is_idempotent(client, payload, database, monkeypatch):
    from app import admin_database
    from app.crear_tablas import main
    from tests.pac_test_support import guard_database
    from sqlalchemy import text
    guard_database(database)
    original = admin_database.create_admin_engine
    identities = []

    def checked_admin():
        admin = original()
        guard_database(admin)
        with admin.connect() as conn:
            identities.append(conn.scalar(text('SELECT current_user')))
        return admin

    monkeypatch.setattr(admin_database, 'create_admin_engine', checked_admin)
    assert client.post('/patients', json=payload).status_code == 201
    main()
    assert client.get('/patients').json()['total'] == 1
    assert identities == ['pac_test_admin']
