import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

def get_db():
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not set. Check your .env file.")
    return psycopg2.connect(url)

# ────────────────────────────────────────────────
# Connection settings – CHANGE THESE to match your PostgreSQL setup
# ────────────────────────────────────────────────




# ================= AUTH TABLES =================
def init_auth_tables():
    con = get_db()
    cur = con.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id BIGSERIAL PRIMARY KEY,
        username TEXT UNIQUE,
        password TEXT,
        role TEXT
    );
    """)

    # Default admin (using ON CONFLICT DO NOTHING)
    cur.execute("""
        INSERT INTO users (username, password, role)
        VALUES ('admin', 'admin123', 'admin')
        ON CONFLICT (username) DO NOTHING;
    """)

    # Default team users
    cur.execute("""
        INSERT INTO users (username, password, role)
        VALUES 
            ('asad',   'asad123',   'team'),
            ('faisal', 'faisal123', 'team')
        ON CONFLICT (username) DO NOTHING;
    """)

    con.commit()
    con.close()


# ================= LOGIN CHECK =================
def validate_user(username, password):
    con = get_db()
    cur = con.cursor()

    cur.execute(
        """
        SELECT id, username, role 
        FROM users 
        WHERE username = %s AND password = %s
        """,
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
    # If you have a separate inventory_db module → call it
    try:
        from inventory_db import init_inventory_tables as _init_inv
    except (ImportError, ModuleNotFoundError):
        # fallback: create minimal doctors & lenses tables
        con = get_db()
        cur = con.cursor()

        cur.execute("""
        CREATE TABLE IF NOT EXISTS doctors (
            id BIGSERIAL PRIMARY KEY,
            name TEXT UNIQUE NOT NULL
        );
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS lenses (
            id BIGSERIAL PRIMARY KEY,
            name TEXT UNIQUE NOT NULL
        );
        """)

        con.commit()
        con.close()
    else:
        _init_inv()

    # ────────────────────────────────────────────────
    # Ensure transactional tables exist
    # ────────────────────────────────────────────────
    con = get_db()
    cur = con.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS stock_transactions (
        id BIGSERIAL PRIMARY KEY,
        lens_id BIGINT NOT NULL,
        doctor_id BIGINT,
        power TEXT NOT NULL,
        quantity INTEGER NOT NULL,
        type TEXT CHECK(type IN ('IN','OUT')) NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        CONSTRAINT fk_lens FOREIGN KEY (lens_id) REFERENCES lenses(id),
        CONSTRAINT fk_doctor FOREIGN KEY (doctor_id) REFERENCES doctors(id)
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS employee_deliveries (
        id BIGSERIAL PRIMARY KEY,
        employee TEXT NOT NULL,
        lens_id BIGINT NOT NULL,
        doctor_id BIGINT,
        power TEXT NOT NULL,
        quantity INTEGER NOT NULL,
        delivered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        CONSTRAINT fk_lens FOREIGN KEY (lens_id) REFERENCES lenses(id),
        CONSTRAINT fk_doctor FOREIGN KEY (doctor_id) REFERENCES doctors(id)
    );
    """)

    con.commit()
    con.close()
