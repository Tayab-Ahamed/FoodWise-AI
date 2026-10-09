import csv
import json
import os
from pathlib import Path
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from .schemas import Record

ROOT = Path(__file__).resolve().parents[2]


def now():
    return datetime.now(timezone.utc).isoformat()


def identifier(prefix):
    import uuid
    return f"{prefix}-{uuid.uuid4().hex[:16]}"


def database_path():
    filename = "foodwise.sqlite3" if demo_enabled() else "operations.sqlite3"
    return Path(os.getenv("FOODWISE_DB", str(ROOT / "backend" / filename)))


def demo_enabled():
    return os.getenv("FOODWISE_DEMO", "true").lower() == "true"


@contextmanager
def connect(write=False):
    conn = sqlite3.connect(database_path(), timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        if write:
            conn.execute("BEGIN IMMEDIATE")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def payload(row):
    return json.loads(row["payload"])


def put(conn, table, obj):
    conn.execute(f"INSERT OR REPLACE INTO {table}(id,payload) VALUES (?,?)", (obj["id"], json.dumps(obj, allow_nan=False)))


def get(conn, table, id):
    row = conn.execute(f"SELECT payload FROM {table} WHERE id=?", (id,)).fetchone()
    return payload(row) if row else None


def all_objects(conn, table):
    return [payload(r) for r in conn.execute(f"SELECT payload FROM {table} ORDER BY rowid DESC")]


def version(conn):
    return int(conn.execute("SELECT value FROM meta WHERE key='version'").fetchone()[0])


def bump(conn):
    value = version(conn) + 1
    conn.execute("UPDATE meta SET value=? WHERE key='version'", (str(value),))
    return value


def records(conn):
    return [payload(r) for r in conn.execute("SELECT payload FROM records ORDER BY json_extract(payload,'$.date'),id")]


def load_csv(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        result = []
        for row in csv.DictReader(f):
            row["attendance"] = int(row["attendance"])
            result.append(Record.model_validate(row).model_dump(mode="json"))
        return result


def seed(conn):
    for table in ["records", "forecasts", "plans", "batches", "handoffs", "previews", "inventory", "audit", "archived_records", "decisions", "trials", "reuse_plans", "acceptances", "coach_reports"]:
        conn.execute(f"DELETE FROM {table}")
    for row in load_csv(ROOT / "data" / "history_90_days.csv"):
        conn.execute("INSERT INTO records(id,kind,plan_id,payload) VALUES (?,'history',NULL,?)", (row["record_id"], json.dumps(row)))
    for row in json.loads((ROOT / "data" / "inventory.json").read_text()):
        put(conn, "inventory", {**row, "id": row["batch_id"]})
    bump(conn)
    conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES ('dataset_source','synthetic')")
    conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES ('demo_seeded','true')")


def bootstrap(reset=False):
    database_path().parent.mkdir(parents=True, exist_ok=True)
    with connect() as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value TEXT NOT NULL)")
        conn.execute("CREATE TABLE IF NOT EXISTS records(id TEXT PRIMARY KEY,kind TEXT NOT NULL,plan_id TEXT,payload TEXT NOT NULL)")
        for table in ["forecasts", "plans", "batches", "handoffs", "previews", "inventory", "audit", "archived_records", "decisions", "trials", "reuse_plans", "recipients", "acceptances", "coach_reports", "directory_snapshots"]:
            conn.execute(f"CREATE TABLE IF NOT EXISTS {table}(id TEXT PRIMARY KEY,payload TEXT NOT NULL)")
        conn.execute("INSERT OR IGNORE INTO meta(key,value) VALUES ('version','0')")
        conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES ('schema_version','2')")
        if reset or (version(conn) == 0 and demo_enabled()):
            seed(conn)
        elif version(conn) == 0:
            bump(conn)
            conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES ('dataset_source','empty')")
            conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES ('demo_seeded','false')")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true")
    args = parser.parse_args()
    bootstrap(args.reset)
    print(f"SQLite initialized: {database_path()}")
