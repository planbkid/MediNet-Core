from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import Patient
from app.schemas import PatientCreate, PatientPatch


def get_patient(db: Session, patient_id: int) -> Patient:
    patient = db.get(Patient, patient_id)
    if patient is None:
        raise HTTPException(404, "Paciente no encontrado")
    return patient


def commit_patient(db: Session, patient: Patient) -> Patient:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        # El nombre se verificó en la tabla real y se conserva en las migraciones.
        if (getattr(exc.orig, "sqlstate", None) == "23505"
                and getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
                == "patients_run_key"):
            raise HTTPException(409, "Ya existe un paciente con ese RUN") from None
        raise HTTPException(500, "No se pudo guardar el paciente") from None
    except SQLAlchemyError:
        # Una escritura fallida debe deshacerse antes de reutilizar la sesión.
        # El manejador global distingue indisponibilidad de errores internos.
        db.rollback()
        raise
    db.refresh(patient)
    return patient


def create_patient(db: Session, payload: PatientCreate) -> Patient:
    patient = Patient(**payload.model_dump())
    db.add(patient)
    return commit_patient(db, patient)


def patch_patient(db: Session, patient_id: int, payload: PatientPatch) -> Patient:
    patient = get_patient(db, patient_id)
    current = {key: getattr(patient, key) for key in PatientCreate.model_fields}
    try:
        validated = PatientCreate.model_validate(current | payload.model_dump(exclude_unset=True))
    except ValidationError:
        raise HTTPException(422, "Los datos resultantes del paciente no son válidos") from None
    # Actualizar solo lo enviado, después de validar el estado completo.
    for key in payload.model_fields_set:
        setattr(patient, key, getattr(validated, key))
    return commit_patient(db, patient)


def literal_prefix(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


def list_patients(db: Session, *, run=None, apellido_paterno=None,
                  apellido_materno=None, prevision=None, page=1, page_size=20):
    filters = []
    if run is not None:
        filters.append(Patient.run == run)
    for column, value in ((Patient.apellido_paterno, apellido_paterno),
                          (Patient.apellido_materno, apellido_materno)):
        if value is not None:
            # lower se calcula en PostgreSQL tanto para el índice como para el parámetro.
            filters.append(func.lower(column).like(func.lower(literal_prefix(value)), escape="\\"))
    if prevision is not None:
        filters.append(Patient.prevision == prevision)
    total = db.scalar(select(func.count()).select_from(Patient).where(*filters))
    items = db.scalars(
        select(Patient).where(*filters)
        .order_by(Patient.apellido_paterno, Patient.apellido_materno.nulls_last(), Patient.id)
        .offset((page - 1) * page_size).limit(page_size)
    ).all()
    return {"items": items, "total": total, "page": page, "page_size": page_size}
