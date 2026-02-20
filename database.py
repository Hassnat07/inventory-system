import sqlite3

DB_FILE = "invoices.db"

def get_db():
    return sqlite3.connect(DB_FILE)


# ================= AUTH TABLES =================
def init_auth_tables():
    con = get_db()
    cur = con.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT,
        role TEXT
    )
    """)

    # Default admin
    cur.execute("""
        INSERT OR IGNORE INTO users (username, password, role)
        VALUES ('admin', 'admin123', 'admin')
    """)

    # Default team user
    cur.execute("""
        INSERT OR IGNORE INTO users (username, password, role)
        VALUES 
        ('asad', 'asad123', 'team'),
        ('faisal', 'faisal123', 'team')
    """)

    con.commit()
    con.close()


# ================= LOGIN CHECK =================
def validate_user(username, password):
    con = get_db()
    cur = con.cursor()

    cur.execute(
        "SELECT id, username, role FROM users WHERE username=? AND password=?",
        (username, password)
    )

    row = cur.fetchone()
    con.close()

    if row:
        return {
            "id": row[0],
            "username": row[1],
            "role": row[2]
        }

    return None
# ================= INVENTORY TABLES =================
def init_inventory_tables():
    # Delegate detailed inventory schema to inventory_db which contains the
    # full lenses schema (power_range, brand, category). Then ensure the
    # additional transactional tables exist.
    try:
        from inventory_db import init_inventory_tables as _init_inv
    except Exception:
        # fallback: create minimal tables here
        con = get_db()
        cur = con.cursor()

        cur.execute("""
        CREATE TABLE IF NOT EXISTS doctors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS lenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL
        )
        """)

        con.commit()
        con.close()
    else:
        _init_inv()

    # Ensure transactional tables exist (non-destructive if already present)
    con = get_db()
    cur = con.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS stock_transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        lens_id INTEGER NOT NULL,
        doctor_id INTEGER,
        power TEXT NOT NULL,
        quantity INTEGER NOT NULL,
        type TEXT CHECK(type IN ('IN','OUT')) NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (lens_id) REFERENCES lenses(id),
        FOREIGN KEY (doctor_id) REFERENCES doctors(id)
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS employee_deliveries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        employee TEXT NOT NULL,
        lens_id INTEGER NOT NULL,
        doctor_id INTEGER,
        power TEXT NOT NULL,
        quantity INTEGER NOT NULL,
        delivered_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (lens_id) REFERENCES lenses(id),
        FOREIGN KEY (doctor_id) REFERENCES doctors(id)
    )
    """)

    con.commit()
    con.close()