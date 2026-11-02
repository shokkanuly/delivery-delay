from pathlib import Path
import sqlite3

import pytest
from sqlalchemy import create_engine, inspect, text

from db.migrate import upgrade
from migrations.legacy_schema import Base as LegacyBase


def test_new_database_and_repeated_upgrade(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'new.db'}")
    upgrade(engine)
    upgrade(engine)
    assert set(LegacyBase.metadata.tables) <= set(inspect(engine).get_table_names())
    with engine.connect() as conn:
        assert conn.execute(text("select version_num from alembic_version")).scalar()


def test_populated_legacy_database_and_backup_restore(tmp_path):
    path = tmp_path / "old.db"
    engine = create_engine(f"sqlite:///{path}")
    LegacyBase.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(text("insert into suppliers(id,name) values ('real-1','Keep me')"))
        conn.execute(text("insert into projects(id,name) values ('site-1','Keep site')"))
        conn.execute(text("insert into deliveries(id,supplier_id,project_id,material_type,route_type,order_date,promised_date) values (7,'real-1','site-1','rebar','local','2026-11-01','2026-11-02')"))
    with sqlite3.connect(path) as source, sqlite3.connect(tmp_path / "backup.db") as target:
        source.backup(target)
    upgrade(engine)
    with engine.connect() as conn:
        assert conn.execute(text("select supplier_id, project_id from deliveries where id=7")).one() == ('real-1', 'site-1')
    restored = create_engine(f"sqlite:///{tmp_path / 'backup.db'}")
    upgrade(restored)
    with restored.connect() as conn:
        assert conn.execute(text("select name from suppliers where id='real-1'")).scalar() == 'Keep me'


def test_refuses_to_stamp_drifted_database(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'drift.db'}")
    with engine.begin() as conn:
        conn.execute(text("create table suppliers (id varchar primary key, name integer)"))
    with pytest.raises(RuntimeError, match="schema drift"):
        upgrade(engine)
