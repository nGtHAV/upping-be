import sqlite3
import os
from typing import List, Dict, Any

DB = os.environ.get("DB_PATH", "uptime.db")

def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db() -> None:
    conn = get_connection()
    c = conn.cursor()
    
    # Create new users table
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            full_name TEXT NOT NULL DEFAULT '',
            tier TEXT NOT NULL DEFAULT 'FREE',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    
    # Create refresh tokens table
    c.execute("""
        CREATE TABLE IF NOT EXISTS refresh_tokens (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            token_hash TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    
    # Existing tables
    c.execute("""
        CREATE TABLE IF NOT EXISTS sites (
            id TEXT PRIMARY KEY,
            name TEXT,
            url TEXT,
            status TEXT DEFAULT 'UNKNOWN',
            response_time INT DEFAULT 0,
            last_checked TEXT,
            added_at TEXT,
            user_id TEXT NOT NULL DEFAULT '',
            is_active BOOLEAN NOT NULL DEFAULT 1
        )
    """)
    
    # Safely alter existing sites table if they don't have new columns
    try:
        c.execute("ALTER TABLE sites ADD COLUMN user_id TEXT NOT NULL DEFAULT ''")
    except sqlite3.OperationalError:
        pass
    try:
        c.execute("ALTER TABLE sites ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT 1")
    except sqlite3.OperationalError:
        pass

    c.execute("""
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            site_id TEXT,
            site_name TEXT,
            url TEXT,
            status TEXT,
            response_time INT,
            http_code INT,
            error TEXT,
            checked_at TEXT,
            user_id TEXT NOT NULL DEFAULT ''
        )
    """)
    
    # Safely alter logs table
    try:
        c.execute("ALTER TABLE logs ADD COLUMN user_id TEXT NOT NULL DEFAULT ''")
    except sqlite3.OperationalError:
        pass

    conn.commit()
    conn.close()

def create_user(user_id: str, email: str, password_hash: str, full_name: str, created_at: str) -> dict:
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        INSERT INTO users (id, email, password_hash, full_name, tier, created_at, updated_at)
        VALUES (?, ?, ?, ?, 'FREE', ?, ?)
    """, (user_id, email, password_hash, full_name, created_at, created_at))
    conn.commit()
    c.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    user = dict(c.fetchone())
    conn.close()
    return user

def get_user_by_email(email: str) -> dict | None:
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE email = ?", (email,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None

def get_user_by_id(user_id: str) -> dict | None:
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None

def update_user(user_id: str, **fields) -> dict:
    if not fields:
        return get_user_by_id(user_id)
    
    conn = get_connection()
    c = conn.cursor()
    set_clauses = ", ".join([f"{k} = ?" for k in fields.keys()])
    values = list(fields.values()) + [user_id]
    
    c.execute(f"UPDATE users SET {set_clauses} WHERE id = ?", values)
    conn.commit()
    c.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    user = dict(c.fetchone())
    conn.close()
    return user

def update_user_tier(user_id: str, tier: str) -> None:
    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE users SET tier = ? WHERE id = ?", (tier, user_id))
    conn.commit()
    conn.close()

def store_refresh_token(token_id: str, user_id: str, token_hash: str, expires_at: str, created_at: str) -> None:
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        INSERT INTO refresh_tokens (id, user_id, token_hash, expires_at, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, (token_id, user_id, token_hash, expires_at, created_at))
    conn.commit()
    conn.close()

def get_refresh_token(token_hash: str) -> dict | None:
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM refresh_tokens WHERE token_hash = ?", (token_hash,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None

def delete_refresh_token(token_hash: str) -> None:
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM refresh_tokens WHERE token_hash = ?", (token_hash,))
    conn.commit()
    conn.close()

def delete_all_user_refresh_tokens(user_id: str) -> None:
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM refresh_tokens WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def get_sites(user_id: str) -> list[dict]:
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM sites WHERE user_id = ? AND is_active = 1", (user_id,))
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_all_sites_for_user(user_id: str) -> list[dict]:
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM sites WHERE user_id = ?", (user_id,))
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_site_count(user_id: str) -> int:
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) as count FROM sites WHERE user_id = ? AND is_active = 1", (user_id,))
    row = c.fetchone()
    conn.close()
    return row["count"]

def get_logs(user_id: str, limit: int = 100) -> list[dict]:
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM logs WHERE user_id = ? ORDER BY checked_at DESC LIMIT ?", (user_id, limit))
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def delete_old_logs(user_id: str, retention_days: int) -> int:
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM logs WHERE user_id = ? AND checked_at < datetime('now', ?)", (user_id, f'-{retention_days} days'))
    count = c.rowcount
    conn.commit()
    conn.close()
    return count

def upsert_site_status(site_id: str, status: str, response_time: int, last_checked: str) -> None:
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        UPDATE sites 
        SET status = ?, response_time = ?, last_checked = ? 
        WHERE id = ?
    """, (status, response_time, last_checked, site_id))
    conn.commit()
    conn.close()

def insert_log(site_id: str, site_name: str, url: str, status: str, response_time: int, http_code: int | None, error: str | None, checked_at: str, user_id: str) -> None:
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        INSERT INTO logs (site_id, site_name, url, status, response_time, http_code, error, checked_at, user_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (site_id, site_name, url, status, response_time, http_code, error, checked_at, user_id))
    conn.commit()
    conn.close()

def add_site_db(site_id: str, name: str, url: str, added_at: str, user_id: str) -> None:
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        INSERT INTO sites (id, name, url, status, response_time, last_checked, added_at, user_id, is_active)
        VALUES (?, ?, ?, 'UNKNOWN', 0, NULL, ?, ?, 1)
    """, (site_id, name, url, added_at, user_id))
    conn.commit()
    conn.close()

def delete_site_db(site_id: str, user_id: str) -> None:
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM sites WHERE id = ? AND user_id = ?", (site_id, user_id))
    c.execute("DELETE FROM logs WHERE site_id = ? AND user_id = ?", (site_id, user_id))
    conn.commit()
    conn.close()

def reactivate_site_db(site_id: str, user_id: str) -> None:
    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE sites SET is_active = 1 WHERE id = ? AND user_id = ?", (site_id, user_id))
    conn.commit()
    conn.close()

def deactivate_site_db(site_id: str, user_id: str) -> None:
    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE sites SET is_active = 0 WHERE id = ? AND user_id = ?", (site_id, user_id))
    conn.commit()
    conn.close()
