from sqlalchemy.orm import DeclarativeBase


# Importar los modelos no debe cargar contraseñas ni construir conexiones.
class Base(DeclarativeBase):
    pass
