from alembic import context

from app import models  # noqa: F401
from app.db_base import Base

if context.is_offline_mode():
    raise RuntimeError("Las migraciones requieren inspección online del esquema existente")

def run(connection):
    context.configure(connection=connection, target_metadata=Base.metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


provided = context.config.attributes.get("connection")
if provided is not None:
    run(provided)
else:
    from app.admin_database import create_admin_engine

    admin_engine = create_admin_engine()
    try:
        with admin_engine.connect() as connection:
            run(connection)
    finally:
        admin_engine.dispose()
