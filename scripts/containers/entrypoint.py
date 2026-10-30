"""Adaptador exclusivo de contenedores; la API nunca carga secretos administrativos."""
import os
from pathlib import Path
import sys


def load_secret(variable, filename):
    value = Path('/run/secrets/' + filename).read_text().strip()
    if not value:
        raise RuntimeError('Secreto vacío')
    os.environ[variable] = value


if sys.argv[1:] == ['api']:
    load_secret('PAC_DB_PASSWORD', 'api_password')
    if any(key in os.environ for key in ('POSTGRES_USER', 'POSTGRES_PASSWORD')):
        raise RuntimeError('La API no debe recibir credenciales administrativas')
    os.execvp('python', ['python', '-m', 'uvicorn', 'app.main:app', '--host',
                        '0.0.0.0', '--port', '8000', '--no-access-log'])
elif sys.argv[1:] == ['admin']:
    load_secret('POSTGRES_PASSWORD', 'admin_password')
    load_secret('PAC_DB_PASSWORD', 'api_password')
    os.execvp('python', ['python', '-m', 'container_tools.prepare_database'])
else:
    raise SystemExit('Modo permitido: api o admin')
