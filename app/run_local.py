"""Arranque local con contraseña oculta y sin leer el .env administrativo."""
import argparse
import getpass
import os
import subprocess
import sys
import warnings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db-host", default="127.0.0.1")
    parser.add_argument("--db-port", type=int, default=5433)
    parser.add_argument("--db-name", default="medinet_pac")
    parser.add_argument("--db-user", default="medinet_pac_api")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    # No permitir el fallback de getpass a una entrada visible.
    with warnings.catch_warnings():
        warnings.simplefilter("error", getpass.GetPassWarning)
        try:
            password = getpass.getpass("Contraseña PostgreSQL de PAC: ")
        except getpass.GetPassWarning:
            parser.exit(1, "Se requiere una terminal con entrada oculta.\n")
    if not password:
        parser.exit(1, "La contraseña no puede estar vacía.\n")
    env = {key: value for key, value in os.environ.items()
           if not key.startswith(("POSTGRES_", "PAC_DB_"))}
    env.update(POSTGRES_DB=args.db_name, DB_HOST=args.db_host,
               DB_PORT=str(args.db_port), PAC_DB_USER=args.db_user,
               PAC_DB_PASSWORD=password)
    # El secreto viaja en el entorno del hijo, nunca en sus argumentos.
    result = subprocess.run(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1",
         "--port", str(args.port), "--no-access-log"], env=env,
    )
    raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
