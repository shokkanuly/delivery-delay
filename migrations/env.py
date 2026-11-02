"""Migrations use DATABASE_URL; credentials never belong in alembic.ini."""
from alembic import context
from sqlalchemy import create_engine
from db.database import Base, DATABASE_URL
import db.models  # noqa: F401

config = context.config


def migrate(connection):
    context.configure(connection=connection, target_metadata=Base.metadata,
                      compare_type=True, render_as_batch=connection.dialect.name == "sqlite")
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    context.configure(url=DATABASE_URL, target_metadata=Base.metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
elif config.attributes.get("connection") is not None:
    migrate(config.attributes["connection"])
else:
    with create_engine(DATABASE_URL).connect() as connection:
        migrate(connection)
