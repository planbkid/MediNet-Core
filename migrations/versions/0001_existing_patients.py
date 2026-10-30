"""Base del Paso 2; adopta solo una tabla existente compatible, sin stamp."""
import re

from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def baseline_table():
    return sa.Table(
        "patients", sa.MetaData(),
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("run", sa.String(10), nullable=False),
        sa.Column("nombres", sa.String(100), nullable=False),
        sa.Column("apellido_paterno", sa.String(60), nullable=False),
        sa.Column("apellido_materno", sa.String(60)),
        sa.Column("fecha_nacimiento", sa.Date, nullable=False),
        sa.Column("prevision", sa.String(10), nullable=False),
        sa.Column("email", sa.String(254)),
        sa.Column("telefono", sa.String(15)),
        sa.Column("direccion", sa.String(200)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("run", name="patients_run_key"),
        sa.CheckConstraint("prevision IN ('FONASA', 'ISAPRE', 'CAPREDENA', 'DIPRECA')", name="ck_patients_prevision"),
        sa.CheckConstraint("run ~ '^[0-9]{7,8}-[0-9K]$'", name="ck_patients_run_formato"),
    )


def canonical_check(value):
    value = re.sub(r"::(?:character varying|text)(?:\[\])?", "", value)
    value = re.sub(r"\s+", "", value)
    return value.replace("=ANY(ARRAY[", "IN(").replace("])", ")")


def validate_existing(bind, table):
    inspector = sa.inspect(bind)
    actual = {column["name"]: column for column in inspector.get_columns("patients")}
    if set(actual) != set(table.c.keys()):
        raise RuntimeError("patients incompatible: revisar columnas antes de migrar")
    for expected in table.c:
        found = actual[expected.name]
        same_type = (found["type"].compile(bind.dialect) == expected.type.compile(bind.dialect))
        if not same_type or found["nullable"] != expected.nullable:
            raise RuntimeError("patients incompatible: revisar tipos y nulabilidad")
    if inspector.get_pk_constraint("patients")["constrained_columns"] != ["id"]:
        raise RuntimeError("patients incompatible: clave primaria")
    if not (actual["id"].get("identity") or "nextval(" in (actual["id"].get("default") or "")):
        raise RuntimeError("patients incompatible: falta generación automática de ID")
    for name in ("created_at", "updated_at"):
        if actual[name].get("default") not in ("now()", "CURRENT_TIMESTAMP"):
            raise RuntimeError("patients incompatible: marcas de tiempo sin valor predeterminado")
    unique = inspector.get_unique_constraints("patients")
    if not any(c["name"] == "patients_run_key" and c["column_names"] == ["run"] for c in unique):
        raise RuntimeError("patients incompatible: UNIQUE de RUN")
    checks = {c["name"]: canonical_check(c["sqltext"]) for c in inspector.get_check_constraints("patients")}
    for constraint in table.constraints:
        if isinstance(constraint, sa.CheckConstraint):
            if checks.get(constraint.name) != canonical_check(str(constraint.sqltext)):
                raise RuntimeError("patients incompatible: reglas CHECK")
    indexes = inspector.get_indexes("patients")
    if not any(i["name"] == "ix_patients_apellidos" and i["column_names"] == [
        "apellido_paterno", "apellido_materno"] and not i["unique"] for i in indexes):
        raise RuntimeError("patients incompatible: índice de apellidos")


def upgrade():
    bind = op.get_bind()
    table = baseline_table()
    if sa.inspect(bind).has_table("patients"):
        validate_existing(bind, table)
    else:
        table.create(bind)
        op.create_index("ix_patients_apellidos", "patients", ["apellido_paterno", "apellido_materno"])


def downgrade():
    raise RuntimeError("No se permite eliminar patients con downgrade; conservar datos")
