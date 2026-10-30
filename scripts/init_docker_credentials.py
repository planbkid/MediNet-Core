"""Credenciales nuevas para Compose con archivos, fuera del repositorio y sin salida secreta."""
import argparse
import os
from pathlib import Path
import secrets

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path, help='Directorio absoluto NUEVO fuera del repositorio')
    args = parser.parse_args()
    if not args.directory.is_absolute():
        parser.error('Usar una ruta absoluta')
    target = args.directory.resolve()
    if target == ROOT or ROOT in target.parents:
        parser.error('Los secretos deben quedar fuera del repositorio y del contexto')
    # No reemplazar directorios existentes ni credenciales de una base inicializada.
    target.mkdir(mode=0o700)
    for name in ('admin_password', 'api_password'):
        fd = os.open(target / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o400)
        with os.fdopen(fd, 'w') as file:
            file.write(secrets.token_urlsafe(40))
            file.flush()
            # Compose monta el archivo sin remapear uid/gid. El directorio 0700
            # impide acceso de otros usuarios del host; cada servicio monta solo lo concedido.
            os.fchmod(file.fileno(), 0o444)
    print('Dos credenciales nuevas creadas fuera del repositorio; directorio 0700, archivos 0444.')


if __name__ == '__main__':
    main()
