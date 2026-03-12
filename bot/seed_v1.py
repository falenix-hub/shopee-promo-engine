import os
import sqlite3
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')
DB_PATH = BASE_DIR / 'data' / 'promo_engine.db'
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()
cur.executescript('''
CREATE TABLE IF NOT EXISTS state (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS watchlist (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    label TEXT,
    short_link TEXT NOT NULL,
    category TEXT DEFAULT 'general',
    reason TEXT DEFAULT '',
    price_previous TEXT DEFAULT '',
    price_current TEXT DEFAULT '',
    active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_type TEXT,
    label TEXT,
    short_link TEXT NOT NULL,
    category TEXT,
    reason TEXT,
    posted_at TEXT DEFAULT CURRENT_TIMESTAMP,
    telegram_message_id TEXT
);
''')
cur.execute("INSERT INTO state(key, value) VALUES('auto_mode','on') ON CONFLICT(key) DO UPDATE SET value='on'")
cur.execute("DELETE FROM watchlist")
cur.execute(
    "INSERT INTO watchlist(label, short_link, category, reason, price_previous, price_current, active) VALUES(?,?,?,?,?,?,1)",
    (
        'Himalaya Brightening Vitamin C - Orange Face Serum 15ml',
        'https://s.shopee.co.id/7VBbZivajq',
        'beauty',
        'Cocok buat yang lagi cari serum vitamin C dengan rating bagus dan harga promo.',
        'Rp61.800',
        'Rp29.285'
    )
)
conn.commit()
conn.close()
print('SEEDED_OK')
