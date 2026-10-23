"""Tiny SQLite store so analyses can be reopened and chat has context."""
import json
import os
import sqlite3
import uuid

DB = os.path.join(os.path.dirname(__file__), "laps.db")


def _conn():
    c = sqlite3.connect(DB)
    c.execute("CREATE TABLE IF NOT EXISTS analyses (id TEXT PRIMARY KEY, created TEXT DEFAULT CURRENT_TIMESTAMP, data TEXT)")
    return c


def save(analysis: dict) -> str:
    aid = uuid.uuid4().hex[:10]
    with _conn() as c:
        c.execute("INSERT INTO analyses (id, data) VALUES (?, ?)", (aid, json.dumps(analysis)))
    return aid


def load(aid: str):
    with _conn() as c:
        row = c.execute("SELECT data FROM analyses WHERE id = ?", (aid,)).fetchone()
    return json.loads(row[0]) if row else None
