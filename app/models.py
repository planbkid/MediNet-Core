from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, DateTime, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db_base import Base


class Patient(Base):
    __tablename__ = "patients"

    id: Mapped[int] = mapped_column(primary_key=True)
    run: Mapped[str] = mapped_column(String(10), unique=True, nullable=False)
    nombres: Mapped[str] = mapped_column(String(100), nullable=False)
    apellido_paterno: Mapped[str] = mapped_column(String(60), nullable=False)
    apellido_materno: Mapped[str | None] = mapped_column(String(60))
    fecha_nacimiento: Mapped[date] = mapped_column(Date, nullable=False)
    prevision: Mapped[str] = mapped_column(String(10), nullable=False)
    email: Mapped[str | None] = mapped_column(String(254))
    telefono: Mapped[str | None] = mapped_column(String(15))
    direccion: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
        onupdate=func.now(), nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "prevision IN ('FONASA', 'ISAPRE', 'CAPREDENA', 'DIPRECA')",
            name="ck_patients_prevision",
        ),
        CheckConstraint(
            "run ~ '^[0-9]{7,8}-[0-9K]$'",
            name="ck_patients_run_formato",
        ),
        Index("ix_patients_apellidos", "apellido_paterno", "apellido_materno"),
        Index("ix_patients_paterno_prefix", func.lower(apellido_paterno).label("paterno_lower"),
              postgresql_ops={"paterno_lower": "text_pattern_ops"}),
        Index("ix_patients_materno_prefix", func.lower(apellido_materno).label("materno_lower"),
              postgresql_ops={"materno_lower": "text_pattern_ops"}),
    )
