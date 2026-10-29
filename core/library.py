"""Local trainer library (SQLite)."""

import os
import sqlite3
import time

DB_PATH = os.path.expanduser("~/.trainerdeck/library.db")
TRAINER_DIR = os.path.expanduser("~/.trainerdeck/trainers")


def _conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    os.makedirs(TRAINER_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init():
    conn = _conn()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS trainers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game TEXT NOT NULL,
            sgdb_id INTEGER,
            trainer_slug TEXT,
            filename TEXT NOT NULL,
            version TEXT,
            path TEXT NOT NULL,
            size INTEGER,
            added_at TEXT,
            appid INTEGER
        )
        """
    )
    conn.commit()
    conn.close()


def add_trainer(game, sgdb_id, trainer_slug, filename, version, path, size, appid=None):
    conn = _conn()
    cur = conn.execute(
        "INSERT INTO trainers (game, sgdb_id, trainer_slug, filename, version, path, size, added_at, appid) VALUES (?,?,?,?,?,?,?,?,?)",
        (game, sgdb_id, trainer_slug, filename, version, path, size, time.strftime("%Y-%m-%d %H:%M:%S"), appid),
    )
    conn.commit()
    rid = cur.lastrowid
    conn.close()
    return rid


def list_trainers():
    conn = _conn()
    rows = conn.execute("SELECT * FROM trainers ORDER BY added_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_trainer(tid: int):
    conn = _conn()
    row = conn.execute("SELECT * FROM trainers WHERE id=?", (tid,)).fetchone()
    conn.close()
    if row:
        try:
            os.remove(row["path"])
        except Exception:
            pass
    conn = _conn()
    conn.execute("DELETE FROM trainers WHERE id=?", (tid,))
    conn.commit()
    conn.close()


def get_trainer(tid: int):
    conn = _conn()
    row = conn.execute("SELECT * FROM trainers WHERE id=?", (tid,)).fetchone()
    conn.close()
    return dict(row) if row else None
