"""Explicit migration runner, also used before startup. Existing baseline is verified, not guessed."""
from pathlib import Path
from alembic import command
from alembic.config import Config


def upgrade(engine):
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    with engine.begin() as connection:
        if connection.dialect.name == "postgresql":
            from sqlalchemy import text
            connection.execute(text("SELECT pg_advisory_xact_lock(731042601)"))
        config.attributes["connection"] = connection
        command.upgrade(config, "head")


if __name__ == "__main__":
    from db.database import engine
    upgrade(engine)
