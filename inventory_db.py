# inventory_db.py — PostgreSQL version (Railway compatible)
# init_db() creates all inventory tables in PostgreSQL via DATABASE_URL

def init_db():
    """Create all inventory tables in PostgreSQL. Safe to call on every startup."""
    import os
    import psycopg2

    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    url = os.getenv("DATABASE_URL", "")
    if not url:
        raise RuntimeError("DATABASE_URL is not set.")
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)

    con = psycopg2.connect(url)
    cur = con.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS lenses (
        id          BIGSERIAL PRIMARY KEY,
        name        TEXT NOT NULL UNIQUE,
        power_range TEXT,
        brand       TEXT,
        category    TEXT,
        status      TEXT DEFAULT 'active',
        created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS doctors (
        id         BIGSERIAL PRIMARY KEY,
        name       TEXT NOT NULL UNIQUE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS inventory_stock (
        lens_id            BIGINT NOT NULL,
        power              TEXT NOT NULL DEFAULT '',
        quantity_available NUMERIC(10,2) NOT NULL DEFAULT 0,
        reorder_level      NUMERIC(10,2) NOT NULL DEFAULT 10,
        last_updated       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (lens_id, power),
        FOREIGN KEY (lens_id) REFERENCES lenses(id) ON DELETE CASCADE
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS stock_in (
        id            BIGSERIAL PRIMARY KEY,
        lens_id       BIGINT NOT NULL,
        power         TEXT NOT NULL,
        quantity      NUMERIC(10,2) NOT NULL,
        supplier      TEXT,
        purchase_date DATE DEFAULT CURRENT_DATE,
        added_by      BIGINT,
        remarks       TEXT,
        created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (lens_id) REFERENCES lenses(id)
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS stock_out (
        id            BIGSERIAL PRIMARY KEY,
        lens_id       BIGINT NOT NULL,
        power         TEXT NOT NULL,
        quantity      NUMERIC(10,2) NOT NULL,
        user_id       BIGINT NOT NULL,
        doctor_id     BIGINT,
        invoice_no    TEXT,
        delivery_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        remarks       TEXT,
        created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (lens_id)   REFERENCES lenses(id),
        FOREIGN KEY (doctor_id) REFERENCES doctors(id)
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS employee_deliveries (
        id         BIGSERIAL PRIMARY KEY,
        username   TEXT NOT NULL,
        lens_id    BIGINT,
        doctor_id  BIGINT,
        power      TEXT,
        quantity   NUMERIC(10,2),
        action     TEXT DEFAULT 'OUT',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (lens_id)   REFERENCES lenses(id),
        FOREIGN KEY (doctor_id) REFERENCES doctors(id)
    )
    """)

    # Safe migrations — add missing columns without breaking existing data
    cur.execute("""
        DO $$ BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='employee_deliveries' AND column_name='action'
            ) THEN
                ALTER TABLE employee_deliveries ADD COLUMN action TEXT DEFAULT 'OUT';
            END IF;
        END $$
    """)

    cur.execute("""
        DO $$ BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='lenses' AND column_name='brand'
            ) THEN
                ALTER TABLE lenses ADD COLUMN brand TEXT;
            END IF;
        END $$
    """)

    # Performance indexes
    cur.execute("CREATE INDEX IF NOT EXISTS idx_stock_in_lens_power  ON stock_in(lens_id, power)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_stock_out_lens_power ON stock_out(lens_id, power)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_emp_del_username     ON employee_deliveries(username)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_emp_del_action       ON employee_deliveries(action)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_inv_stock_lens       ON inventory_stock(lens_id)")

    con.commit()
    cur.close()
    con.close()
