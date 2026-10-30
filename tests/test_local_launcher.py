"""Arranque: secretos fuera de argv y sin herencia administrativa al hijo."""
import getpass
from types import SimpleNamespace
import warnings

import pytest

from app import run_local


def test_launcher_separates_environment(monkeypatch):
    monkeypatch.setattr('sys.argv', ['run_local', '--port', '8001'])
    monkeypatch.setenv('POSTGRES_USER', 'administrator-must-not-leak')
    monkeypatch.setenv('POSTGRES_PASSWORD', 'admin-test-only')
    monkeypatch.setenv('PAC_DB_PASSWORD', 'stale-test-only')
    monkeypatch.setattr(getpass, 'getpass', lambda prompt: 'input-test-only')
    captured = []

    def run(argv, *, env):
        captured.append((argv, env))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(run_local.subprocess, 'run', run)
    with pytest.raises(SystemExit) as result:
        run_local.main()
    assert result.value.code == 0
    argv, env = captured[0]
    assert env['PAC_DB_USER'] == 'medinet_pac_api'
    assert env['PAC_DB_PASSWORD'] == 'input-test-only'
    assert env['POSTGRES_DB'] == 'medinet_pac'
    assert 'POSTGRES_USER' not in env and 'POSTGRES_PASSWORD' not in env
    assert not any('test-only' in arg for arg in argv)
    assert '--no-access-log' in argv


@pytest.mark.parametrize('unsafe', ['empty', 'visible'])
def test_launcher_aborts_without_hidden_nonempty_password(monkeypatch, unsafe):
    monkeypatch.setattr('sys.argv', ['run_local'])

    def prompt(message):
        if unsafe == 'visible':
            warnings.warn('No hidden terminal', getpass.GetPassWarning)
        return ''

    monkeypatch.setattr(getpass, 'getpass', prompt)
    monkeypatch.setattr(run_local.subprocess, 'run', lambda *a, **kw: pytest.fail('No iniciar API'))
    with pytest.raises(SystemExit) as result:
        run_local.main()
    assert result.value.code == 1
