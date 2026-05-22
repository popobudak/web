# database.py
import sqlite3
from datetime import datetime

DB_FILE = "keys.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS keys (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    secret_key TEXT UNIQUE NOT NULL,
                    created_at TEXT,
                    used INTEGER DEFAULT 0,
                    used_at TEXT,
                    used_by_id INTEGER,
                    used_by_username TEXT,
                    used_by_name TEXT
                )''')
    
    conn.commit()
    conn.close()
    print("✅ Database keys.db siap")


def generate_key():
    import random, string
    key = "IVAS-" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=20))
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("INSERT INTO keys (secret_key, created_at) VALUES (?, ?)", (key, now))
    conn.commit()
    conn.close()
    return key


def check_key_and_bind(secret_key: str, chat_id: int, username: str = None, first_name: str = None):
    """Cek kunci dan bind ke user (sekali pakai)"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    c.execute("SELECT used FROM keys WHERE secret_key=?", (secret_key,))
    result = c.fetchone()
    
    if not result or result[0] == 1:
        conn.close()
        return False
    
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("""UPDATE keys 
                 SET used=1, used_at=?, used_by_id=?, used_by_username=?, used_by_name=? 
                 WHERE secret_key=?""", 
             (now, chat_id, username, first_name, secret_key))
    conn.commit()
    conn.close()
    return True


def get_all_keys():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT secret_key, used, used_by_username, used_by_name FROM keys ORDER BY id DESC")
    data = c.fetchall()
    conn.close()
    return data