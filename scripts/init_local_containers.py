"""Crear secretos nuevos de Podman sin imprimirlos; no reemplazar recursos previos."""
from pathlib import Path
import secrets
import socket
import subprocess

ROOT = Path(__file__).resolve().parents[1]
PREFIX = 'medinet-pac-local-20261030'


def main():
    # Abortar ante cualquier colisión antes de crear secretos.
    for kind, names in {
        'container': [PREFIX + '-db', PREFIX + '-api'],
        'volume': [PREFIX + '-pgdata'],
        'network': [PREFIX + '-backend', PREFIX + '-frontend'],
        'secret': [PREFIX + '-admin', PREFIX + '-api'],
    }.items():
        for name in names:
            result = subprocess.run(['podman', kind, 'inspect', name], capture_output=True)
            if result.returncode == 0:
                raise SystemExit('Recurso ya existente: ' + name + '; no se modifica.')
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 18081))
    config = ROOT / '.env.containers'
    if config.exists():
        raise SystemExit('.env.containers ya existe; revisar antes de inicializar.')
    for suffix in ('admin', 'api'):
        result = subprocess.run(['podman', 'secret', 'create', PREFIX + '-' + suffix, '-'],
                                input=secrets.token_urlsafe(40).encode(), capture_output=True)
        if result.returncode:
            raise SystemExit('No se pudo crear el secreto ' + suffix + '; no se reemplaza ninguno.')
    with config.open('x') as file:
        file.write('PAC_LOCAL_PORT=18081\n')
    config.chmod(0o600)
    print('Dos secretos exclusivos creados en Podman; configuración local sin contraseñas.')


if __name__ == '__main__':
    main()
