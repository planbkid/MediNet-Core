"""Regresiones con sesiones simuladas; incluidas en el runner de pruebas aisladas."""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError, OperationalError, ProgrammingError, TimeoutError

from app.database import get_db
from app.main import app
from app.services.patients import commit_patient


@pytest.mark.parametrize('error, status, detail', [
    (ProgrammingError('private SQL', {}, Exception('private')), 500, 'Error interno'),
    (OperationalError('private SQL', {}, Exception('private')), 503, 'Base de datos no disponible'),
    (OperationalError('private SQL', {}, SimpleNamespace(sqlstate='40P01')), 500, 'Error interno'),
    (OperationalError('private SQL', {}, SimpleNamespace(sqlstate='08006')), 503, 'Base de datos no disponible'),
    (TimeoutError('private'), 503, 'Base de datos no disponible'),
])
def test_sqlalchemy_errors_are_classified_and_sanitized(error, status, detail):
    def failed_dependency():
        raise error
        yield  # La dependencia mantiene el contrato de generador sin abrir sesiones.

    app.dependency_overrides[get_db] = failed_dependency
    try:
        with TestClient(app) as client:
            response = client.get('/patients')
        assert response.status_code == status
        assert response.json() == {'detail': detail}
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.parametrize('error', [
    OperationalError('private SQL', {}, Exception('private')),
    ProgrammingError('private SQL', {}, Exception('private')),
])
def test_failed_write_rolls_back_before_propagating(error):
    db = Mock()
    db.commit.side_effect = error
    with pytest.raises(type(error)) as caught:
        commit_patient(db, object())
    assert caught.value is error
    db.rollback.assert_called_once_with()
    db.refresh.assert_not_called()


@pytest.mark.parametrize('constraint, status', [('patients_run_key', 409), ('other_key', 500)])
def test_only_run_unique_conflict_is_409(constraint, status):
    db = Mock()
    db.commit.side_effect = IntegrityError('private SQL', {}, SimpleNamespace(
        sqlstate='23505', diag=SimpleNamespace(constraint_name=constraint)))
    with pytest.raises(HTTPException) as caught:
        commit_patient(db, object())
    assert caught.value.status_code == status
    db.rollback.assert_called_once_with()
