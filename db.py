"""SQLite storage for conversations and messages."""
import json
import sqlite3
import uuid
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path("data/chat.db")


def _conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def init():
    with closing(_conn()) as c, c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS conversations (
            id TEXT PRIMARY KEY, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id TEXT NOT NULL REFERENCES conversations(id),
            role TEXT NOT NULL,            -- 'user' or 'assistant'
            content TEXT NOT NULL,
            sources_json TEXT,             -- assistant only
            status TEXT,                   -- assistant only: 'answered' or 'not_found'
            created_at TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conversation_id, id);
        """)


def create_conversation() -> str:
    cid = uuid.uuid4().hex
    with closing(_conn()) as c, c:
        c.execute("INSERT INTO conversations VALUES (?, ?)", (cid, _now()))
    return cid


def conversation_exists(cid: str) -> bool:
    with closing(_conn()) as c:
        return c.execute("SELECT 1 FROM conversations WHERE id = ?", (cid,)).fetchone() is not None


def add_message(cid: str, role: str, content: str, sources=None, status=None):
    with closing(_conn()) as c, c:
        c.execute("INSERT INTO messages (conversation_id, role, content, sources_json, status, created_at) "
                  "VALUES (?, ?, ?, ?, ?, ?)",
                  (cid, role, content, json.dumps(sources) if sources is not None else None, status, _now()))


def get_history(cid: str, limit: int) -> list[dict]:
    """Last `limit` messages, oldest first."""
    with closing(_conn()) as c:
        rows = c.execute("SELECT role, content FROM messages WHERE conversation_id = ? "
                         "ORDER BY id DESC LIMIT ?", (cid, limit)).fetchall()
    return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]
    