"""
SQLite Storage Manager for Sticky Notes.
Provides ACID-compliant, robust persistence using Python's built-in sqlite3.
"""

import os
import json
import time
import uuid
import sqlite3
from typing import Dict, List, Any, Optional

DEFAULT_DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "notes.db")
LEGACY_JSON_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "notes_data.json")

class StorageManager:
    def __init__(self, db_path: str = DEFAULT_DB_FILE):
        self.db_path = db_path
        self._init_db()
        if self.db_path == DEFAULT_DB_FILE:
            self._migrate_from_json_if_needed()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Create notes table and indexes if they do not exist."""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS notes (
                    id TEXT PRIMARY KEY,
                    text TEXT DEFAULT '',
                    formatting TEXT DEFAULT '[]',
                    x INTEGER DEFAULT 350,
                    y INTEGER DEFAULT 180,
                    width INTEGER DEFAULT 280,
                    height INTEGER DEFAULT 240,
                    color TEXT DEFAULT 'yellow',
                    is_pinned INTEGER DEFAULT 0,
                    is_collapsed INTEGER DEFAULT 0,
                    is_deleted INTEGER DEFAULT 0,
                    created_at TEXT,
                    updated_at TEXT
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_notes_deleted ON notes(is_deleted)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_notes_updated ON notes(updated_at)")

    def _migrate_from_json_if_needed(self):
        """Migrate existing notes from legacy JSON file if notes table is empty."""
        try:
            with self._get_connection() as conn:
                count = conn.execute("SELECT COUNT(*) FROM notes").fetchone()[0]
                if count == 0 and os.path.exists(LEGACY_JSON_FILE):
                    with open(LEGACY_JSON_FILE, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    notes_dict = data.get("notes", {})
                    for n in notes_dict.values():
                        fmt = json.dumps(n.get("formatting", []))
                        conn.execute("""
                            INSERT OR IGNORE INTO notes 
                            (id, text, formatting, x, y, width, height, color, is_pinned, is_collapsed, is_deleted, created_at, updated_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            n.get("id"),
                            n.get("text", ""),
                            fmt,
                            n.get("x", 350),
                            n.get("y", 180),
                            n.get("width", 280),
                            n.get("height", 240),
                            n.get("color", "yellow"),
                            1 if n.get("is_pinned", False) else 0,
                            1 if n.get("is_collapsed", False) else 0,
                            1 if n.get("is_deleted", False) else 0,
                            n.get("created_at", time.strftime("%Y-%m-%d %H:%M:%S")),
                            n.get("updated_at", time.strftime("%Y-%m-%d %H:%M:%S"))
                        ))
                    conn.commit()
        except Exception as e:
            print(f"Migration note: {e}")

    def _row_to_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        """Convert SQLite Row to dictionary matching app format."""
        formatting_raw = row["formatting"]
        try:
            formatting = json.loads(formatting_raw) if formatting_raw else []
        except Exception:
            formatting = []

        return {
            "id": row["id"],
            "text": row["text"],
            "formatting": formatting,
            "x": row["x"],
            "y": row["y"],
            "width": row["width"],
            "height": row["height"],
            "color": row["color"],
            "is_pinned": bool(row["is_pinned"]),
            "is_collapsed": bool(row["is_collapsed"]),
            "is_deleted": bool(row["is_deleted"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"]
        }

    def create_note(
        self,
        text: str = "",
        x: int = 350,
        y: int = 180,
        width: int = 280,
        height: int = 240,
        color: str = "yellow",
        is_pinned: bool = False
    ) -> Dict[str, Any]:
        """Create a new sticky note entry in SQLite database."""
        note_id = f"note_{uuid.uuid4().hex[:10]}"
        now = time.strftime("%Y-%m-%d %H:%M:%S")
        formatting_str = "[]"

        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO notes 
                (id, text, formatting, x, y, width, height, color, is_pinned, is_collapsed, is_deleted, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
            """, (
                note_id, text, formatting_str, x, y, width, height, color,
                1 if is_pinned else 0, 0, now, now
            ))
            conn.commit()

        return {
            "id": note_id,
            "text": text,
            "formatting": [],
            "x": x,
            "y": y,
            "width": width,
            "height": height,
            "color": color,
            "is_pinned": is_pinned,
            "is_collapsed": False,
            "is_deleted": False,
            "created_at": now,
            "updated_at": now
        }

    def update_note(self, note_id: str, **kwargs):
        """Update fields for a specific note."""
        if not kwargs:
            return

        fields = []
        values = []
        now = time.strftime("%Y-%m-%d %H:%M:%S")

        for key, val in kwargs.items():
            if key == "formatting":
                fields.append("formatting = ?")
                values.append(json.dumps(val) if isinstance(val, list) else "[]")
            elif key in ["is_pinned", "is_collapsed", "is_deleted"]:
                fields.append(f"{key} = ?")
                values.append(1 if val else 0)
            elif key in ["text", "x", "y", "width", "height", "color"]:
                fields.append(f"{key} = ?")
                values.append(val)

        fields.append("updated_at = ?")
        values.append(now)

        values.append(note_id)

        sql = f"UPDATE notes SET {', '.join(fields)} WHERE id = ?"
        with self._get_connection() as conn:
            conn.execute(sql, values)
            conn.commit()

    def get_note(self, note_id: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM notes WHERE id = ?", (note_id,)).fetchone()
            if row:
                return self._row_to_dict(row)
        return None

    def get_active_notes(self) -> List[Dict[str, Any]]:
        """Return all notes that are not marked deleted, newest updated first."""
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM notes WHERE is_deleted = 0 ORDER BY updated_at DESC"
            ).fetchall()
            return [self._row_to_dict(r) for r in rows]

    def get_all_notes(self) -> List[Dict[str, Any]]:
        """Return all notes including deleted/archived."""
        with self._get_connection() as conn:
            rows = conn.execute("SELECT * FROM notes ORDER BY updated_at DESC").fetchall()
            return [self._row_to_dict(r) for r in rows]

    def soft_delete_note(self, note_id: str):
        """Mark note as deleted."""
        now = time.strftime("%Y-%m-%d %H:%M:%S")
        with self._get_connection() as conn:
            conn.execute("UPDATE notes SET is_deleted = 1, updated_at = ? WHERE id = ?", (now, note_id))
            conn.commit()

    def permanently_delete_note(self, note_id: str):
        """Permanently remove a note from SQLite database."""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM notes WHERE id = ?", (note_id,))
            conn.commit()

    def restore_note(self, note_id: str):
        """Restore a previously deleted note."""
        now = time.strftime("%Y-%m-%d %H:%M:%S")
        with self._get_connection() as conn:
            conn.execute("UPDATE notes SET is_deleted = 0, updated_at = ? WHERE id = ?", (now, note_id))
            conn.commit()
