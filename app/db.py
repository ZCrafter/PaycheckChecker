"""Tiny SQLite store for weekly hours and 'already notified' markers."""
import sqlite3
from datetime import date, datetime
from pathlib import Path


class DB:
    def __init__(self, data_dir: Path):
        data_dir.mkdir(parents=True, exist_ok=True)
        self.path = data_dir / "hours.db"
        with self._conn() as c:
            c.execute(
                "CREATE TABLE IF NOT EXISTS weeks ("
                "week_ending TEXT PRIMARY KEY, regular REAL NOT NULL, "
                "overtime REAL NOT NULL, updated_at TEXT NOT NULL)"
            )
            c.execute("CREATE TABLE IF NOT EXISTS events (key TEXT PRIMARY KEY)")

    def _conn(self):
        return sqlite3.connect(self.path)

    def save_week(self, week_ending: date, regular: float, overtime: float):
        with self._conn() as c:
            c.execute(
                "INSERT INTO weeks(week_ending, regular, overtime, updated_at) VALUES(?,?,?,?) "
                "ON CONFLICT(week_ending) DO UPDATE SET regular=excluded.regular, "
                "overtime=excluded.overtime, updated_at=excluded.updated_at",
                (week_ending.isoformat(), regular, overtime, datetime.now().isoformat(timespec="seconds")),
            )

    def get_week(self, week_ending: date):
        with self._conn() as c:
            row = c.execute(
                "SELECT regular, overtime FROM weeks WHERE week_ending=?", (week_ending.isoformat(),)
            ).fetchone()
        return {"regular": row[0], "overtime": row[1]} if row else None

    def delete_last(self):
        """Deletes the most recently updated entry; returns it (or None)."""
        with self._conn() as c:
            row = c.execute(
                "SELECT week_ending, regular, overtime FROM weeks ORDER BY updated_at DESC LIMIT 1"
            ).fetchone()
            if row:
                c.execute("DELETE FROM weeks WHERE week_ending=?", (row[0],))
        return {"week_ending": date.fromisoformat(row[0]), "regular": row[1], "overtime": row[2]} if row else None

    def recent_weeks(self, limit: int = 8):
        with self._conn() as c:
            rows = c.execute(
                "SELECT week_ending, regular, overtime FROM weeks ORDER BY week_ending DESC LIMIT ?", (limit,)
            ).fetchall()
        return [{"week_ending": date.fromisoformat(r[0]), "regular": r[1], "overtime": r[2]} for r in rows]

    def seen(self, key: str) -> bool:
        with self._conn() as c:
            return c.execute("SELECT 1 FROM events WHERE key=?", (key,)).fetchone() is not None

    def mark(self, key: str):
        with self._conn() as c:
            c.execute("INSERT OR IGNORE INTO events(key) VALUES(?)", (key,))
