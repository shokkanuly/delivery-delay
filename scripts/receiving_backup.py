"""Consistent backups include private attachments stored in the database. Restore into an empty target."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess

from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import make_url


def pg_environment(url):
    env = dict(os.environ, PGHOST=url.host or "localhost", PGPORT=str(url.port or 5432),
               PGUSER=url.username or "postgres", PGDATABASE=url.database,
               PGPASSWORD=url.password or "")
    if url.query.get("sslmode"):
        env["PGSSLMODE"] = url.query["sslmode"]
    return env


def backup(database_url, output):
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(fd)
    url = make_url(database_url)
    try:
        if url.get_backend_name() == "sqlite":
            if not url.database or not Path(url.database).is_file():
                raise ValueError("Source database does not exist")
            with sqlite3.connect(url.database) as source, sqlite3.connect(path) as target:
                source.backup(target)
                if target.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    raise RuntimeError("Backup integrity check failed")
        elif url.get_backend_name() == "postgresql":
            subprocess.run(["pg_dump", "--format=custom", "--no-owner", "--no-acl", "--file", str(path)],
                           env=pg_environment(url), check=True, capture_output=True)
        else:
            raise ValueError("Only SQLite and Postgres backups are supported")
        manifest = {"sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "bytes": path.stat().st_size,
                    "format": url.get_backend_name(), "includes": "database and receipt attachment bytes"}
        manifest_path = Path(str(path) + ".json")
        with os.fdopen(os.open(manifest_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as out:
            json.dump(manifest, out, indent=2)
        return manifest
    except Exception:
        path.unlink(missing_ok=True)
        raise


def restore(database_url, source):
    path = Path(source)
    manifest = json.loads(Path(str(path) + ".json").read_text())
    if hashlib.sha256(path.read_bytes()).hexdigest() != manifest["sha256"]:
        raise ValueError("Backup digest mismatch")
    url = make_url(database_url)
    if url.get_backend_name() != manifest["format"]:
        raise ValueError("Backup and target database formats differ")
    if url.get_backend_name() == "sqlite":
        if Path(url.database).exists():
            raise ValueError("Restore target must be a new SQLite file")
        Path(url.database).parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(url.database, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(fd)
        with sqlite3.connect(path) as origin, sqlite3.connect(url.database) as target:
            origin.backup(target)
    else:
        engine = create_engine(database_url)
        try:
            if inspect(engine).get_table_names():
                raise ValueError("Postgres restore target must be empty")
        finally:
            engine.dispose()
        subprocess.run(["pg_restore", "--no-owner", "--no-acl", "--exit-on-error", "--dbname", url.database, str(path)],
                       env=pg_environment(url), check=True, capture_output=True)
    return {"restored": True, "includes_attachments": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["backup", "restore"])
    parser.add_argument("path")
    args = parser.parse_args()
    from db.database import DATABASE_URL
    try:
        result = backup(DATABASE_URL, args.path) if args.action == "backup" else restore(DATABASE_URL, args.path)
        print(json.dumps(result))
    except subprocess.CalledProcessError:
        raise SystemExit("Postgres backup/restore command failed; inspect server access and client-tool versions. Credentials were not printed.")


if __name__ == "__main__":
    main()
