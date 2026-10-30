"""Crea SOLO un PostgreSQL efímero de pruebas y ejecuta pytest sin secretos en argv."""
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import URL, create_engine, text
from tests.pac_test_support import (
    ADMIN, API, CONTAINER, DATABASE, LABEL, PORT, mark_database, require, verify_container,
)


def main():
    os.chdir(ROOT)
    image = "docker.io/library/postgres:18-alpine"
    require(subprocess.run(["podman", "image", "exists", image]).returncode == 0,
            "Falta la imagen local: no se descargarán imágenes")
    existing = subprocess.run(["podman", "container", "exists", CONTAINER])
    require(existing.returncode == 1, "El nombre ya está ocupado; no se reutiliza ni elimina")
    admin_password, api_password = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    # Aislar también la configuración heredada de la sesión del desarrollador.
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(("POSTGRES_", "PAC_", "DB_"))}
    env.update(POSTGRES_USER=ADMIN, POSTGRES_PASSWORD=admin_password, POSTGRES_DB=DATABASE,
               DB_HOST="127.0.0.1", DB_PORT=str(PORT), PAC_DB_USER=API,
               PAC_DB_PASSWORD=api_password, PAC_TEST_MARKER="pac-test-" + secrets.token_hex(24))
    result = subprocess.run([
        "podman", "run", "-d", "--pull=never", "--name", CONTAINER,
        "--label", "medinet.task=" + LABEL,
        "--env", "POSTGRES_USER", "--env", "POSTGRES_PASSWORD", "--env", "POSTGRES_DB",
        "-p", f"127.0.0.1:{PORT}:5432", "--tmpfs", "/var/lib/postgresql:rw", image,
    ], env=env, capture_output=True, text=True)
    require(result.returncode == 0, "No se pudo crear el contenedor de pruebas (sin recreación)")
    env["PAC_TEST_CONTAINER_ID"] = result.stdout.strip()
    os.environ.update({k: v for k, v in env.items() if k.startswith("PAC_TEST_")})
    verify_container()
    admin = create_engine(URL.create("postgresql+psycopg", username=ADMIN,
        password=admin_password, host="127.0.0.1", port=PORT, database=DATABASE),
        hide_parameters=True, connect_args={"connect_timeout": 2})
    ready = False
    for _ in range(40):
        try:
            with admin.connect() as conn:
                system_id = conn.scalar(text("SELECT system_identifier::text FROM pg_control_system()"))
                require(tuple(conn.execute(text("SELECT current_database(), current_user")).one())
                        == (DATABASE, ADMIN), "Base o administrador inesperados")
                require(conn.scalar(text("SHOW server_version_num")).startswith("18"), "Versión inesperada")
            ready = True
            break
        except Exception:
            time.sleep(0.5)
    require(ready, "PostgreSQL de pruebas no quedó preparado; no se ejecutó pytest")
    # La instancia se acaba de crear; registrar su identidad antes de cualquier migración.
    with admin.begin() as conn:
        mark_database(conn, DATABASE)
    env["PAC_TEST_SYSTEM_ID"] = str(system_id)
    admin.dispose()
    print(f"Pruebas aisladas: {CONTAINER}, 127.0.0.1:{PORT}; sin volumen de desarrollo", flush=True)
    completed = subprocess.run([sys.executable, "-m", "pytest", "-q", "--tb=short", *sys.argv[1:]], env=env)
    # Se conserva para revisión; no detener ni borrar otros recursos.
    print(f"Contenedor de pruebas conservado: {CONTAINER}", flush=True)
    raise SystemExit(completed.returncode)


if __name__ == "__main__":
    main()
