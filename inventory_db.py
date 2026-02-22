# inventory_db.py
from database import get_db


def init_db():
    con = get_db()
    cur = con.cursor()

    # Lenses
    cur.execute("""
    CREATE TABLE IF NOT EXISTS lenses (
        id BIGSERIAL PRIMARY KEY,
        name TEXT NOT NULL UNIQUE,
        power_range TEXT,
        brand TEXT,
        category TEXT,
        status TEXT DEFAULT 'active',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Doctors
    cur.execute("""
    CREATE TABLE IF NOT EXISTS doctors (
        id BIGSERIAL PRIMARY KEY,
        name TEXT NOT NULL UNIQUE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Inventory stock
    cur.execute("""
    CREATE TABLE IF NOT EXISTS inventory_stock (
        lens_id BIGINT NOT NULL,
        power TEXT NOT NULL DEFAULT '',
        quantity_available INTEGER NOT NULL DEFAULT 0,
        reorder_level INTEGER NOT NULL DEFAULT 10,
        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (lens_id, power),
        FOREIGN KEY (lens_id) REFERENCES lenses(id) ON DELETE CASCADE
    )
    """)

    # Stock IN
    cur.execute("""
    CREATE TABLE IF NOT EXISTS stock_in (
        id BIGSERIAL PRIMARY KEY,
        lens_id BIGINT NOT NULL,
        power TEXT NOT NULL,
        quantity INTEGER NOT NULL,
        supplier TEXT,
        purchase_date DATE DEFAULT CURRENT_DATE,
        added_by BIGINT,
        remarks TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (lens_id) REFERENCES lenses(id)
    )
    """)

    # Stock OUT
    cur.execute("""
    CREATE TABLE IF NOT EXISTS stock_out (
        id BIGSERIAL PRIMARY KEY,
        lens_id BIGINT NOT NULL,
        power TEXT NOT NULL,
        quantity INTEGER NOT NULL,
        user_id BIGINT NOT NULL,
        doctor_id BIGINT,
        invoice_no TEXT,
        delivery_date DATE DEFAULT CURRENT_DATE,
        remarks TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (lens_id) REFERENCES lenses(id),
        FOREIGN KEY (doctor_id) REFERENCES doctors(id)
    )
    """)

    con.commit()
    con.close()
