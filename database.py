import logging
import json
import time
from config import DATABASE_URL

_in_memory_users = {}
_in_memory_numbers = [
    {"id": 1, "phone": "+22501020304", "country": "Ivory Coast", "flag": "🇨🇮", "assigned": False, "created_at": "2026-08-31T00:00:00Z"},
    {"id": 2, "phone": "+12025550143", "country": "United States", "flag": "🇺🇸", "assigned": False, "created_at": "2026-08-31T00:00:00Z"},
    {"id": 3, "phone": "+447700900077", "country": "United Kingdom", "flag": "🇬🇧", "assigned": False, "created_at": "2026-08-31T00:00:00Z"},
    {"id": 4, "phone": "+8801712345678", "country": "Bangladesh", "flag": "🇧🇩", "assigned": False, "created_at": "2026-08-31T00:00:00Z"}
]
_in_memory_sms = []
_in_memory_settings = {"bot_active": "1", "panel_mode": "api"}

def get_conn():
    if not DATABASE_URL:
        return None
    import psycopg2
    return psycopg2.connect(DATABASE_URL)

def init_db():
    if not DATABASE_URL:
        logging.info("Using local fast storage for Painite database")
        return
    try:
        import psycopg2
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
        return _in_memory_users.get(str(user_id))
    try:
        import psycopg2.extras
        conn = get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
        row = cur.fetchone()
        cur.close(); conn.close()
        return dict(row) if row else None
    except Exception as e:
        logging.error(f"get_user error: {e}")
        return _in_memory_users.get(str(user_id))

def save_user(user_id: str, username: str, first_name: str, last_number_time: float = 0):
    uid = str(user_id)
    if uid in _in_memory_users:
        _in_memory_users[uid]["username"] = username
        _in_memory_users[uid]["first_name"] = first_name
    else:
        _in_memory_users[uid] = {
            "user_id": uid,
            "username": username,
            "first_name": first_name,
            "last_number_time": last_number_time,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }

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
    uid = str(user_id)
    if uid in _in_memory_users:
        _in_memory_users[uid]["last_number_time"] = ts
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
        return list(_in_memory_users.values())
    try:
        import psycopg2.extras
        conn = get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM users ORDER BY created_at DESC")
        rows = cur.fetchall()
        cur.close(); conn.close()
        return [dict(r) for r in rows] if rows else list(_in_memory_users.values())
    except Exception as e:
        logging.error(f"get_all_users error: {e}")
        return list(_in_memory_users.values())

def add_number(phone: str, country: str = "", flag: str = ""):
    exists = any(n["phone"] == phone for n in _in_memory_numbers)
    if not exists:
        _in_memory_numbers.insert(0, {
            "id": len(_in_memory_numbers) + 1,
            "phone": phone,
            "country": country,
            "flag": flag,
            "assigned": False,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
        })

    if not DATABASE_URL:
        return True
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
        return True

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
        return _in_memory_numbers
    try:
        import psycopg2.extras
        conn = get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM numbers ORDER BY created_at DESC LIMIT 200")
        rows = cur.fetchall()
        cur.close(); conn.close()
        return [dict(r) for r in rows] if rows else _in_memory_numbers
    except Exception as e:
        logging.error(f"get_numbers_list error: {e}")
        return _in_memory_numbers

def get_numbers_count():
    if not DATABASE_URL:
        return len([n for n in _in_memory_numbers if not n.get("assigned")])
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM numbers WHERE assigned = FALSE")
        count = cur.fetchone()[0]
        cur.close(); conn.close()
        return count
    except Exception as e:
        return len([n for n in _in_memory_numbers if not n.get("assigned")])

def get_available_countries():
    if not DATABASE_URL:
        countries_map = {}
        for n in _in_memory_numbers:
            c = n.get("country", "")
            if c:
                countries_map[c] = countries_map.get(c, 0) + 1
        return [{"country": k, "flag": "🌍", "count": v} for k, v in countries_map.items()]
    try:
        import psycopg2.extras
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
        return any(s.get("unique_key") == unique_key for s in _in_memory_sms)
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
    _in_memory_sms.insert(0, {
        "unique_key": unique_key, "phone": phone, "message": message, "otp": otp, "country": country,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
    })
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
        return _in_memory_sms[:limit]
    try:
        import psycopg2.extras
        conn = get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM sent_sms ORDER BY created_at DESC LIMIT %s", (limit,))
        rows = cur.fetchall()
        cur.close(); conn.close()
        return [dict(r) for r in rows] if rows else _in_memory_sms[:limit]
    except Exception as e:
        return _in_memory_sms[:limit]

def get_setting(key: str, default=None):
    if not DATABASE_URL:
        return _in_memory_settings.get(key, default)
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT value FROM settings WHERE key = %s", (key,))
        row = cur.fetchone()
        cur.close(); conn.close()
        return row[0] if row else _in_memory_settings.get(key, default)
    except Exception as e:
        logging.error(f"get_setting error: {e}")
        return _in_memory_settings.get(key, default)

def set_setting(key: str, value: str):
    _in_memory_settings[key] = str(value)
    if not DATABASE_URL:
        return True
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
        return True

def get_all_settings():
    if not DATABASE_URL:
        return dict(_in_memory_settings)
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT key, value FROM settings")
        rows = cur.fetchall()
        cur.close(); conn.close()
        d = dict(_in_memory_settings)
        d.update({k: v for k, v in rows})
        return d
    except Exception as e:
        logging.error(f"get_all_settings error: {e}")
        return dict(_in_memory_settings)

def is_bot_active() -> bool:
    val = get_setting("bot_active", "1")
    return str(val) != "0"

def get_stats():
    users_cnt = len(_in_memory_users)
    num_cnt = len([n for n in _in_memory_numbers if not n.get("assigned")])
    sms_cnt = len(_in_memory_sms)
    if not DATABASE_URL:
        return {"users": users_cnt, "numbers": num_cnt, "sms_sent": sms_cnt}
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
        return {"users": max(users, users_cnt), "numbers": max(numbers, num_cnt), "sms_sent": max(sms_sent, sms_cnt)}
    except Exception as e:
        return {"users": users_cnt, "numbers": num_cnt, "sms_sent": sms_cnt}
