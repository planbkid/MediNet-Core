from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import DisconnectionError, OperationalError, SQLAlchemyError, TimeoutError

from app.routers.patients import router as patients_router


app = FastAPI(
    title="MediNet-Core – Módulo PAC",
    description="Gestión de Pacientes y Admisión (Grupo 6)",
    version="0.1.0",
)

app.include_router(patients_router)


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    # No reflejar datos personales, SQL ni valores recibidos en errores.
    return JSONResponse(status_code=422, content={"detail": [
        {"loc": list(error["loc"]), "type": error["type"],
         "msg": "Valor inválido"} for error in exc.errors()
    ]})


@app.exception_handler(SQLAlchemyError)
async def database_error(request: Request, exc: SQLAlchemyError):
    # SQLAlchemy también informa errores de programación: no todos son caídas.
    sqlstate = getattr(getattr(exc, "orig", None), "sqlstate", None)
    unavailable = isinstance(exc, (DisconnectionError, TimeoutError)) or (
        isinstance(exc, OperationalError)
        and (sqlstate is None or sqlstate.startswith("08")
             or sqlstate in {"57P01", "57P02", "57P03", "53300"})
    )
    return JSONResponse(
        status_code=503 if unavailable else 500,
        content={"detail": "Base de datos no disponible" if unavailable else "Error interno"},
    )


@app.get("/health")
def health():
    return {"status": "ok"}
