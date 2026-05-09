import os
import psycopg2

# Load .env for local development; on Railway DATABASE_URL is set automatically
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def get_db():
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not set. Check your .env file.")
    return psycopg2.connect(url)


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

    cur.execute("""
        INSERT INTO users (username, password, role)
        VALUES ('admin', 'admin123', 'admin')
        ON CONFLICT (username) DO NOTHING;
    """)

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
    try:
        from inventory_db import init_inventory_tables as _init_inv
    except (ImportError, ModuleNotFoundError):
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


# ================= CATALOG & CONFERENCE TABLES =================
def init_catalog_conference_tables():
    con = get_db()
    cur = con.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS catalog_items (
        id BIGSERIAL PRIMARY KEY,
        name TEXT NOT NULL,
        category TEXT NOT NULL,
        description TEXT,
        model_no TEXT,
        image_filename TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS catalog_item_images (
        id BIGSERIAL PRIMARY KEY,
        item_id BIGINT NOT NULL REFERENCES catalog_items(id) ON DELETE CASCADE,
        image_filename TEXT NOT NULL,
        sort_order INTEGER DEFAULT 0
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS conference_images (
        id BIGSERIAL PRIMARY KEY,
        year INTEGER NOT NULL,
        image_filename TEXT NOT NULL,
        caption TEXT,
        sort_order INTEGER DEFAULT 0
    );
    """)

    con.commit()
    con.close()
