# inventory_db.py
import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, "invoices.db")


def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row  # allows row['column'] access
    return conn


def init_db():
    with get_db() as con:
        cur = con.cursor()

        # Lenses
        cur.execute("""
        CREATE TABLE IF NOT EXISTS lenses (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL UNIQUE,
            power_range TEXT,
            brand       TEXT,
            category    TEXT,
            status      TEXT DEFAULT 'active',
            created_at  TEXT DEFAULT (datetime('now'))
        )
        """)

        # Doctors
        cur.execute("""
        CREATE TABLE IF NOT EXISTS doctors (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name       TEXT NOT NULL UNIQUE,
            created_at TEXT DEFAULT (datetime('now'))
        )
        """)

        # Inventory stock – with power column
        cur.execute("""
        CREATE TABLE IF NOT EXISTS inventory_stock (
            lens_id            INTEGER NOT NULL,
            power              TEXT NOT NULL DEFAULT '',
            quantity_available INTEGER NOT NULL DEFAULT 0,
            reorder_level      INTEGER NOT NULL DEFAULT 10,
            last_updated       TEXT DEFAULT (datetime('now')),
            PRIMARY KEY (lens_id, power),
            FOREIGN KEY (lens_id) REFERENCES lenses(id) ON DELETE CASCADE
        )
        """)

        # Stock IN
        cur.execute("""
        CREATE TABLE IF NOT EXISTS stock_in (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            lens_id       INTEGER NOT NULL,
            power         TEXT NOT NULL,
            quantity      INTEGER NOT NULL,
            supplier      TEXT,
            purchase_date TEXT DEFAULT (date('now')),
            added_by      INTEGER,
            remarks       TEXT,
            created_at    TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (lens_id) REFERENCES lenses(id)
        )
        """)

        # Stock OUT
        cur.execute("""
        CREATE TABLE IF NOT EXISTS stock_out (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            lens_id       INTEGER NOT NULL,
            power         TEXT NOT NULL,
            quantity      INTEGER NOT NULL,
            user_id       INTEGER NOT NULL,
            doctor_id     INTEGER,
            invoice_no    TEXT,
            delivery_date TEXT DEFAULT (date('now')),
            remarks       TEXT,
            created_at    TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (lens_id)   REFERENCES lenses(id),
            FOREIGN KEY (doctor_id) REFERENCES doctors(id)
        )
        """)

        # Safe column addition
        def add_column(table, col_name, col_def):
            cur.execute(f"PRAGMA table_info({table})")
            cols = {r[1] for r in cur.fetchall()}
            if col_name not in cols:
                cur.execute(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_def}")

        add_column("inventory_stock", "power",        "TEXT NOT NULL DEFAULT ''")
        add_column("inventory_stock", "last_updated", "TEXT DEFAULT (datetime('now'))")

        con.commit()