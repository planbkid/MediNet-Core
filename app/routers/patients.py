from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Response, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import (
    ErrorResponse, PatientCreate, PatientList, PatientPatch, PatientRead,
    Prevision, Run, RunValidation, RunValidationResult, Surname, clean_run,
)
from app.services import patients

router = APIRouter(prefix="/patients", tags=["Pacientes"], responses={
    503: {"model": ErrorResponse, "description": "Base de datos no disponible"},
})
DB = Annotated[Session, Depends(get_db)]
PatientID = Annotated[int, Path(gt=0, description="ID entero positivo del paciente")]
errors = {404: {"model": ErrorResponse, "description": "Paciente inexistente"},
          409: {"model": ErrorResponse, "description": "RUN ya registrado"},
          500: {"model": ErrorResponse, "description": "Error interno sin datos sensibles"}}


@router.post("/validate-run", response_model=RunValidationResult,
             summary="Validar formato y Módulo 11 sin consultar existencia")
def validate_run(payload: RunValidation):
    try:
        normalized = clean_run(payload.run)
    except ValueError:
        return {"valid": False, "normalized_run": None}
    return {"valid": True, "normalized_run": normalized}


@router.post("", response_model=PatientRead, status_code=201, responses=errors,
             summary="Crear paciente con RUN normalizado")
def create_patient(payload: PatientCreate, response: Response, request: Request, db: DB):
    patient = patients.create_patient(db, payload)
    response.headers["Location"] = str(request.url_for("get_patient", patient_id=patient.id))
    return patient


@router.get("", response_model=PatientList, summary="Buscar y paginar pacientes",
            description="Filtros combinados con AND. Apellidos por prefijo literal, sin distinguir "
                        "mayúsculas; las tildes sí se distinguen. Orden: apellido paterno, materno e ID.")
def list_patients(
    db: DB,
    run: Annotated[Run | None, Query(description="RUN exacto; admite puntos y guion", examples=["12.345.678-5"])] = None,
    apellido_paterno: Annotated[Surname | None, Query(description="Prefijo literal; %, _ y \\ no son comodines")] = None,
    apellido_materno: Annotated[Surname | None, Query(description="Prefijo literal de apellido materno")] = None,
    prevision: Annotated[Prevision | None, Query(description="FONASA, ISAPRE, CAPREDENA o DIPRECA")] = None,
    page: Annotated[int, Query(ge=1, le=100000, description="Página: 1 a 100000; sin resultados devuelve items vacío")] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description="Tamaño: 1 a 100; predeterminado 20")] = 20,
):
    return patients.list_patients(db, run=run, apellido_paterno=apellido_paterno,
                                 apellido_materno=apellido_materno, prevision=prevision,
                                 page=page, page_size=page_size)


@router.get("/{patient_id}", response_model=PatientRead, responses=errors,
            summary="Consultar por ID", name="get_patient")
def get_patient(patient_id: PatientID, db: DB):
    return patients.get_patient(db, patient_id)


@router.patch("/{patient_id}", response_model=PatientRead, responses=errors,
              summary="Actualizar campos enviados",
              description="Ausencia conserva el valor. null solo borra campos opcionales. "
                          "Objeto vacío y null en obligatorios producen 422. RUN se revalida.")
def patch_patient(patient_id: PatientID, payload: PatientPatch, db: DB):
    return patients.patch_patient(db, patient_id, payload)
