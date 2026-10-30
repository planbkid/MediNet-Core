"""Conexión de administración; nunca se importa desde el arranque de la API."""
import os
from pathlib import Path

from dotenv import dotenv_values
from sqlalchemy import URL, create_engine


def create_admin_engine():
    # Leer el archivo sin exportar sus secretos al entorno del proceso.
    # Las variables ya exportadas tienen prioridad, también en las pruebas.
    required = ("POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB", "DB_HOST", "DB_PORT")
    values = dict(os.environ)
    if not all(key in values for key in required):
        values = dotenv_values(Path(__file__).resolve().parents[1] / ".env") | values
    url = URL.create(
        drivername="postgresql+psycopg",
        username=values["POSTGRES_USER"],
        password=values["POSTGRES_PASSWORD"],
        host=values["DB_HOST"],
        port=int(values["DB_PORT"]),
        database=values["POSTGRES_DB"],
    )
    return create_engine(url, pool_pre_ping=True, hide_parameters=True)
