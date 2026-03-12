PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS products (
    product_id TEXT PRIMARY KEY,
    source_url TEXT NOT NULL,
    affiliate_url TEXT,
    name TEXT NOT NULL,
    category TEXT,
    shop_name TEXT,
    shop_id TEXT,
    rating REAL DEFAULT 0,
    sold_count INTEGER DEFAULT 0,
    price_current INTEGER DEFAULT 0,
    price_previous INTEGER DEFAULT 0,
    price_lowest_seen INTEGER DEFAULT 0,
    price_highest_seen INTEGER DEFAULT 0,
    affiliate_enabled INTEGER DEFAULT 0,
    status TEXT DEFAULT 'tracked',
    last_checked_at TEXT,
    last_posted_at TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS price_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id TEXT NOT NULL,
    checked_at TEXT NOT NULL,
    price INTEGER NOT NULL,
    rating REAL DEFAULT 0,
    sold_count INTEGER DEFAULT 0,
    stock_status TEXT,
    note TEXT,
    FOREIGN KEY(product_id) REFERENCES products(product_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_price_history_product_time
ON price_history(product_id, checked_at DESC);

CREATE TABLE IF NOT EXISTS deal_scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id TEXT NOT NULL,
    checked_at TEXT NOT NULL,
    drop_percent REAL DEFAULT 0,
    drop_amount INTEGER DEFAULT 0,
    discount_score REAL DEFAULT 0,
    trust_score REAL DEFAULT 0,
    conversion_score REAL DEFAULT 0,
    freshness_score REAL DEFAULT 0,
    commission_score REAL DEFAULT 0,
    spam_penalty REAL DEFAULT 0,
    final_score REAL DEFAULT 0,
    qualifies INTEGER DEFAULT 0,
    reason TEXT,
    FOREIGN KEY(product_id) REFERENCES products(product_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_deal_scores_product_time
ON deal_scores(product_id, checked_at DESC);

CREATE TABLE IF NOT EXISTS posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id TEXT NOT NULL,
    posted_at TEXT NOT NULL,
    telegram_channel TEXT,
    telegram_message_id TEXT,
    price_at_post INTEGER DEFAULT 0,
    drop_percent REAL DEFAULT 0,
    final_score REAL DEFAULT 0,
    tags_used TEXT,
    post_type TEXT DEFAULT 'deal',
    status TEXT DEFAULT 'sent',
    FOREIGN KEY(product_id) REFERENCES products(product_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_posts_product_time
ON posts(product_id, posted_at DESC);

CREATE TABLE IF NOT EXISTS system_config (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

INSERT OR IGNORE INTO system_config(key, value) VALUES
('min_drop_percent', '10'),
('min_drop_amount', '20000'),
('min_rating', '4.7'),
('min_sold_count', '50'),
('min_final_score', '70'),
('min_hours_between_same_product_posts', '72'),
('max_posts_per_day', '12'),
('max_posts_per_hour', '2');
