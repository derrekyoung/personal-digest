import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "cache.db"


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("CREATE TABLE IF NOT EXISTS seen (video_id TEXT PRIMARY KEY)")
    conn.commit()
    return conn


def is_seen(video_id: str) -> bool:
    with _conn() as conn:
        row = conn.execute("SELECT 1 FROM seen WHERE video_id = ?", (video_id,)).fetchone()
        return row is not None


def mark_seen(video_id: str) -> None:
    with _conn() as conn:
        conn.execute("INSERT OR IGNORE INTO seen VALUES (?)", (video_id,))
        conn.commit()


def filter_unseen(video_ids: list[str]) -> list[str]:
    if not video_ids:
        return []
    with _conn() as conn:
        placeholders = ",".join("?" * len(video_ids))
        seen = {
            row[0]
            for row in conn.execute(
                f"SELECT video_id FROM seen WHERE video_id IN ({placeholders})", video_ids
            )
        }
    return [vid for vid in video_ids if vid not in seen]
