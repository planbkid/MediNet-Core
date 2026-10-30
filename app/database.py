import os
from sqlalchemy import URL, create_engine
from sqlalchemy.orm import sessionmaker

url = URL.create(
    drivername="postgresql+psycopg",
    # No cargar .env administrativo ni usar sus credenciales como alternativa.
    username=os.environ["PAC_DB_USER"],
    password=os.environ["PAC_DB_PASSWORD"],
    host=os.environ["DB_HOST"],
    port=int(os.environ["DB_PORT"]),
    database=os.environ["POSTGRES_DB"],
)

engine = create_engine(url, pool_pre_ping=True, hide_parameters=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False)


def get_db():
    """Una sesión por solicitud; cierre y rollback de trabajo pendiente garantizados."""
    with SessionLocal() as session:
        yield session
