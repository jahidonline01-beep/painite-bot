import psycopg2
import psycopg2.extras
import logging
import json
from config import DATABASE_URL

def get_conn():
    return psycopg2.connect(DATABASE_URL)

def init_db():
    if not DATABASE_URL:
        logging.warning("No DATABASE_URL set, skipping DB init")
        return
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_number_time FLOAT DEFAULT 0,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS numbers (
                id SERIAL PRIMARY KEY,
                phone TEXT UNIQUE NOT NULL,
                country TEXT,
                flag TEXT,
                assigned BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS sent_sms (
                id SERIAL PRIMARY KEY,
                unique_key TEXT UNIQUE NOT NULL,
                phone TEXT,
                message TEXT,
                otp TEXT,
                country TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        conn.commit()
        cur.close()
        conn.close()
        logging.info("Database initialized successfully")
    except Exception as e:
        logging.error(f"DB init error: {e}")

def get_user(user_id: str):
    if not DATABASE_URL:
        return None
    try:
        conn = get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
        row = cur.fetchone()
        cur.close(); conn.close()
        return dict(row) if row else None
    except Exception as e:
        logging.error(f"get_user error: {e}")
        return None

def save_user(user_id: str, username: str, first_name: str, last_number_time: float = 0):
    if not DATABASE_URL:
        return
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO users (user_id, username, first_name, last_number_time)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (user_id) DO UPDATE
            SET username = EXCLUDED.username,
                first_name = EXCLUDED.first_name
        """, (user_id, username, first_name, last_number_time))
        conn.commit()
        cur.close(); conn.close()
    except Exception as e:
        logging.error(f"save_user error: {e}")

def update_user_number_time(user_id: str, ts: float):
    if not DATABASE_URL:
        return
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("UPDATE users SET last_number_time = %s WHERE user_id = %s", (ts, user_id))
        conn.commit()
        cur.close(); conn.close()
    except Exception as e:
        logging.error(f"update_user_number_time error: {e}")

def get_all_users():
    if not DATABASE_URL:
        return []
    try:
        conn = get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM users ORDER BY created_at DESC")
        rows = cur.fetchall()
        cur.close(); conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        logging.error(f"get_all_users error: {e}")
        return []

def add_number(phone: str, country: str = "", flag: str = ""):
    if not DATABASE_URL:
        return False
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO numbers (phone, country, flag)
            VALUES (%s, %s, %s)
            ON CONFLICT (phone) DO NOTHING
        """, (phone, country, flag))
        conn.commit()
        added = cur.rowcount > 0
        cur.close(); conn.close()
        return added
    except Exception as e:
        logging.error(f"add_number error: {e}")
        return False

def delete_number(phone: str):
    if not DATABASE_URL:
        return False
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("DELETE FROM numbers WHERE phone = %s", (phone,))
        conn.commit()
        deleted = cur.rowcount > 0
        cur.close(); conn.close()
        return deleted
    except Exception as e:
        logging.error(f"delete_number error: {e}")
        return False

def get_number(country: str = None):
    if not DATABASE_URL:
        return None
    try:
        conn = get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        if country:
            cur.execute("""
                SELECT * FROM numbers WHERE assigned = FALSE AND country = %s
                ORDER BY created_at ASC LIMIT 1
            """, (country,))
        else:
            cur.execute("""
                SELECT * FROM numbers WHERE assigned = FALSE
                ORDER BY created_at ASC LIMIT 1
            """)
        row = cur.fetchone()
        if row:
            cur.execute("DELETE FROM numbers WHERE id = %s", (row['id'],))
            conn.commit()
        cur.close(); conn.close()
        return dict(row) if row else None
    except Exception as e:
        logging.error(f"get_number error: {e}")
        return None

def get_numbers_list():
    if not DATABASE_URL:
        return []
    try:
        conn = get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM numbers ORDER BY created_at DESC LIMIT 200")
        rows = cur.fetchall()
        cur.close(); conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        logging.error(f"get_numbers_list error: {e}")
        return []

def get_numbers_count():
    if not DATABASE_URL:
        return 0
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM numbers WHERE assigned = FALSE")
        count = cur.fetchone()[0]
        cur.close(); conn.close()
        return count
    except Exception as e:
        return 0

def get_available_countries():
    if not DATABASE_URL:
        return []
    try:
        conn = get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            SELECT country, flag, COUNT(*) as count
            FROM numbers WHERE assigned = FALSE AND country != ''
            GROUP BY country, flag ORDER BY count DESC
        """)
        rows = cur.fetchall()
        cur.close(); conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        logging.error(f"get_available_countries error: {e}")
        return []

def is_sms_sent(unique_key: str):
    if not DATABASE_URL:
        return False
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM sent_sms WHERE unique_key = %s", (unique_key,))
        exists = cur.fetchone() is not None
        cur.close(); conn.close()
        return exists
    except Exception as e:
        return False

def mark_sms_sent(unique_key: str, phone: str, message: str, otp: str, country: str):
    if not DATABASE_URL:
        return
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO sent_sms (unique_key, phone, message, otp, country)
            VALUES (%s, %s, %s, %s, %s) ON CONFLICT DO NOTHING
        """, (unique_key, phone, message, otp, country))
        conn.commit()
        cur.close(); conn.close()
    except Exception as e:
        logging.error(f"mark_sms_sent error: {e}")

def get_sms_log(limit=50):
    if not DATABASE_URL:
        return []
    try:
        conn = get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM sent_sms ORDER BY created_at DESC LIMIT %s", (limit,))
        rows = cur.fetchall()
        cur.close(); conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        return []

def get_setting(key: str, default=None):
    if not DATABASE_URL:
        return default
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT value FROM settings WHERE key = %s", (key,))
        row = cur.fetchone()
        cur.close(); conn.close()
        return row[0] if row else default
    except Exception as e:
        logging.error(f"get_setting error: {e}")
        return default

def set_setting(key: str, value: str):
    if not DATABASE_URL:
        return False
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO settings (key, value) VALUES (%s, %s)
            ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
        """, (key, str(value)))
        conn.commit()
        cur.close(); conn.close()
        return True
    except Exception as e:
        logging.error(f"set_setting error: {e}")
        return False

def get_all_settings():
    if not DATABASE_URL:
        return {}
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT key, value FROM settings")
        rows = cur.fetchall()
        cur.close(); conn.close()
        return {k: v for k, v in rows}
    except Exception as e:
        logging.error(f"get_all_settings error: {e}")
        return {}

def is_bot_active() -> bool:
    val = get_setting("bot_active", "1")
    return str(val) != "0"

def get_stats():
    if not DATABASE_URL:
        return {"users": 0, "numbers": 0, "sms_sent": 0}
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM users")
        users = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM numbers WHERE assigned = FALSE")
        numbers = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM sent_sms")
        sms_sent = cur.fetchone()[0]
        cur.close(); conn.close()
        return {"users": users, "numbers": numbers, "sms_sent": sms_sent}
    except Exception as e:
        return {"users": 0, "numbers": 0, "sms_sent": 0}
