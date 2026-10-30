from pathlib import Path

from alembic import command
from alembic.config import Config


def main():
    # Conserva el comando del Paso 2, usando ahora el historial de migraciones.
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    command.upgrade(config, "head")
    print("Listo: tabla patients y migraciones actualizadas.")


if __name__ == "__main__":
    main()
