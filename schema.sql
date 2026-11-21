-- The two tables behind the app.
-- This file runs every time the app starts; "IF NOT EXISTS" makes that safe.

CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT NOT NULL UNIQUE COLLATE NOCASE,
    password_hash TEXT NOT NULL,
    created_at    TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS items (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT    NOT NULL,
    sku          TEXT    UNIQUE COLLATE NOCASE,  -- optional product code or barcode
    category     TEXT    NOT NULL DEFAULT '',
    price        REAL    NOT NULL DEFAULT 0 CHECK (price >= 0),
    quantity     INTEGER NOT NULL DEFAULT 0 CHECK (quantity >= 0),
    low_stock_at INTEGER NOT NULL DEFAULT 5,     -- flag the item once stock drops to this
    created_at   TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
);
