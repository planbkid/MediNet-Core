"""Barreras antes de migrar o limpiar: nunca aceptar solo un sufijo de nombre."""
import json
import os
import subprocess

from sqlalchemy import text

CONTAINER = "medinet_pac_credentials_test"
DATABASE = "medinet_pac_credentials_test"
PORT = 55434
ADMIN = "pac_test_admin"
API = "pac_test_api"
LABEL = "pac-credentials-tests"


def require(condition, message):
    # No usar assert: estas protecciones también deben existir con python -O.
    if not condition:
        raise RuntimeError(message)


def verify_container():
    result = subprocess.run(["podman", "inspect", CONTAINER], capture_output=True, text=True)
    require(result.returncode == 0, "No se pudo verificar el contenedor exclusivo de pruebas")
    info = json.loads(result.stdout)[0]
    require(info["Id"] == os.environ.get("PAC_TEST_CONTAINER_ID"), "Identidad de contenedor incorrecta")
    require(info["Config"]["Labels"].get("medinet.task") == LABEL, "Etiqueta de pruebas ausente")
    require(info["State"]["Running"], "Contenedor de pruebas detenido")
    ports = info["NetworkSettings"]["Ports"].get("5432/tcp")
    require(ports == [{"HostIp": "127.0.0.1", "HostPort": str(PORT)}], "Puerto de pruebas incorrecto")
    mounts = info.get("Mounts", [])
    require(not any(m.get("Type") in {"volume", "bind"} for m in mounts),
            "Las pruebas no pueden montar volúmenes ni directorios del host")
    # Podman registra --tmpfs en HostConfig; otros motores lo incluyen en Mounts.
    tmpfs = info.get("HostConfig", {}).get("Tmpfs", {})
    require("/var/lib/postgresql" in tmpfs or any(
        m.get("Type") == "tmpfs" and m.get("Destination") == "/var/lib/postgresql"
        for m in mounts), "Falta almacenamiento temporal exclusivo")


def guard_database(engine, expected=DATABASE):
    verify_container()
    require(engine.url.host == "127.0.0.1" and engine.url.port == PORT
            and engine.url.database == expected and engine.url.username == ADMIN,
            "Conexión administrativa fuera del entorno de pruebas")
    with engine.connect() as conn:
        identity = conn.execute(text("""SELECT current_database(), current_user,
            (SELECT system_identifier::text FROM pg_control_system()),
            shobj_description(oid, 'pg_database')
            FROM pg_database WHERE datname=current_database()""")).one()
        require(tuple(identity) == (expected, ADMIN, os.environ.get("PAC_TEST_SYSTEM_ID"),
                                    os.environ.get("PAC_TEST_MARKER")),
                "La base no pertenece a esta ejecución de pruebas")


def mark_database(connection, name):
    # Nombre y marcador provienen del runner, no de entradas de la API.
    from psycopg import sql
    connection.exec_driver_sql(sql.SQL("COMMENT ON DATABASE {} IS {}").format(
        sql.Identifier(name), sql.Literal(os.environ["PAC_TEST_MARKER"])
    ).as_string())
