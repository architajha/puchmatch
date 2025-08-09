# database.py
import sqlite3
from typing import List, Optional, Tuple, Dict
from config import DATABASE_FILE

def get_conn():
    return sqlite3.connect(DATABASE_FILE, check_same_thread=False)

def init_db():
    """Create the users table if it doesn't exist. Call this once at app startup."""
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            name TEXT,
            interests TEXT
        )
    """)
    conn.commit()
    conn.close()

def add_or_update_user(user_id: str, name: str = None, interests: str = None) -> None:
    """
    Insert a new user or update existing one.
    'interests' is stored as a comma-separated string, e.g. "music,cricket,aeromodelling"
    """
    conn = get_conn()
    c = conn.cursor()
    # Upsert style
    c.execute("""
        INSERT INTO users (user_id, name, interests)
        VALUES (?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            name=excluded.name,
            interests=excluded.interests
    """, (user_id, name, interests))
    conn.commit()
    conn.close()

def get_user(user_id: str) -> Optional[Tuple[str, str, str]]:
    """Return a tuple (user_id, name, interests) or None"""
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT user_id, name, interests FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row

def delete_user(user_id: str) -> None:
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def get_all_users() -> List[Tuple[str, str, str]]:
    """Return list of tuples (user_id, name, interests)"""
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT user_id, name, interests FROM users")
    rows = c.fetchall()
    conn.close()
    return rows
