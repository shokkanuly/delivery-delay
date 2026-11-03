"""Adopt the frozen pre-migration schema without dropping or rewriting data."""
from alembic import op
from sqlalchemy import inspect
from migrations.legacy_schema import Base

revision = "0001_legacy"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = inspect(bind)
    existing = set(inspector.get_table_names())
    for name, table in Base.metadata.tables.items():
        if name not in existing:
            continue
        columns = {c["name"]: c for c in inspector.get_columns(name)}
        for col in table.columns:
            actual = columns.get(col.name)
            if actual is None or actual["type"]._type_affinity is not col.type._type_affinity:
                raise RuntimeError(f"Legacy schema drift at {name}.{col.name}; reconcile before upgrading")
        if set(inspector.get_pk_constraint(name)["constrained_columns"]) != set(table.primary_key.columns.keys()):
            raise RuntimeError(f"Legacy primary key drift at {name}")
        expected_unique = {tuple(c.columns.keys()) for c in table.constraints
                           if c.__class__.__name__ == "UniqueConstraint"}
        actual_unique = {tuple(c["column_names"]) for c in inspector.get_unique_constraints(name)}
        if not expected_unique <= actual_unique:
            raise RuntimeError(f"Legacy unique constraint drift at {name}")
    Base.metadata.create_all(bind=bind, checkfirst=True)


def downgrade():
    raise RuntimeError("Destructive baseline downgrade disabled; restore a verified backup instead")
