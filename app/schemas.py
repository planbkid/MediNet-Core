import re
import unicodedata
from datetime import date, datetime
from typing import Annotated, Literal

from email_validator import EmailNotValidError, validate_email
from pydantic import (
    BaseModel, BeforeValidator, ConfigDict, Field, StringConstraints,
    field_validator, model_validator,
)

from app.validators.run import normalize_run


def clean_text(value):
    if not isinstance(value, str):
        return value
    if any(unicodedata.category(char).startswith("C") for char in value):
        raise ValueError("No se permiten caracteres de control")
    return " ".join(unicodedata.normalize("NFC", value).split())


def clean_run(value):
    if not isinstance(value, str):
        raise ValueError("RUN debe ser texto")
    if any(unicodedata.category(char).startswith("C") for char in value):
        raise ValueError("RUN contiene caracteres no permitidos")
    return normalize_run(value)


def clean_prevision(value):
    return clean_text(value).upper() if isinstance(value, str) else value


def clean_email(value):
    value = clean_text(value)
    if value is None or not isinstance(value, str):
        return value
    try:
        parsed = validate_email(value, check_deliverability=False)
    except EmailNotValidError:
        raise ValueError("Email inválido") from None
    return value.rsplit("@", 1)[0] + "@" + parsed.domain.lower()


def clean_phone(value):
    if value is None or not isinstance(value, str):
        return value
    value = clean_text(value)
    if not re.fullmatch(r"\+?[0-9 ()-]+", value):
        raise ValueError("Teléfono: usar dígitos y separadores de presentación")
    return re.sub(r"[^0-9]", "", value)


Run = Annotated[str, BeforeValidator(clean_run)]
Name = Annotated[str, StringConstraints(min_length=1, max_length=100), BeforeValidator(clean_text)]
Surname = Annotated[str, StringConstraints(min_length=1, max_length=60), BeforeValidator(clean_text)]
Prevision = Annotated[
    Literal["FONASA", "ISAPRE", "CAPREDENA", "DIPRECA"], BeforeValidator(clean_prevision)
]
Email = Annotated[str, StringConstraints(min_length=1, max_length=254), BeforeValidator(clean_email)]
Phone = Annotated[str, StringConstraints(min_length=1, max_length=15), BeforeValidator(clean_phone)]
Address = Annotated[str, StringConstraints(min_length=1, max_length=200), BeforeValidator(clean_text)]


class InputModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PatientCreate(InputModel):
    run: Run = Field(examples=["12.345.678-5"])
    nombres: Name = Field(examples=["Ana María"])
    apellido_paterno: Surname = Field(examples=["Muñoz"])
    apellido_materno: Surname | None = None
    fecha_nacimiento: date = Field(examples=["1990-05-10"])
    prevision: Prevision
    email: Email | None = None
    telefono: Phone | None = None
    direccion: Address | None = None

    @field_validator("fecha_nacimiento")
    @classmethod
    def birth_not_future(cls, value):
        if value > date.today():
            raise ValueError("La fecha de nacimiento no puede ser futura")
        return value


class PatientPatch(InputModel):
    run: Run | None = None
    nombres: Name | None = None
    apellido_paterno: Surname | None = None
    apellido_materno: Surname | None = None
    fecha_nacimiento: date | None = None
    prevision: Prevision | None = None
    email: Email | None = None
    telefono: Phone | None = None
    direccion: Address | None = None

    @model_validator(mode="before")
    @classmethod
    def patch_rules(cls, values):
        if isinstance(values, dict):
            if not values:
                raise ValueError("Enviar al menos un campo")
            for key in ("run", "nombres", "apellido_paterno", "fecha_nacimiento", "prevision"):
                if key in values and values[key] is None:
                    raise ValueError(f"{key} no permite null")
        return values

    @field_validator("fecha_nacimiento")
    @classmethod
    def birth_not_future(cls, value):
        return PatientCreate.birth_not_future(value) if value is not None else value


class PatientRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    run: str
    nombres: str
    apellido_paterno: str
    apellido_materno: str | None
    fecha_nacimiento: date
    prevision: str
    email: str | None
    telefono: str | None
    direccion: str | None
    created_at: datetime
    updated_at: datetime


class PatientList(BaseModel):
    items: list[PatientRead]
    total: int
    page: int
    page_size: int


class RunValidation(InputModel):
    run: str = Field(strict=True, examples=["12.345.678-5"])


class RunValidationResult(BaseModel):
    valid: bool
    normalized_run: str | None


class ErrorResponse(BaseModel):
    detail: str
