from flask import Flask, render_template, request, send_file
import sqlite3
from flask import flash

import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, g
from generate_pdf import generate_pdf
from auth_routes import auth_bp
from database import init_auth_tables, init_inventory_tables
from flask import g


# ---------------- APP SETUP ----------------


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, "invoices.db")
PDF_DIR = os.path.join(BASE_DIR, "generated_pdfs")
os.makedirs(PDF_DIR, exist_ok=True)
app = Flask(__name__)
app.register_blueprint(auth_bp, url_prefix='/')
app.secret_key = "ramay-electromedics-secret-key"

from flask import request, redirect, url_for
#from inventory_routes import inventory_bp
#from inventory_db import init_inventory_tables

#app.register_blueprint(inventory_bp)
init_inventory_tables()
PUBLIC_ROUTES = ["/", "/login", "/static"]

@app.route("/admin")
def admin_dashboard():
    if g.user is None or g.user.get("role") != "admin":
        return redirect(url_for("index"))

    return render_template("admin_dashboard.html")




@app.before_request
def load_logged_in_user():
    g.user = None
    if "user_id" in session:
        g.user = {
            "id": session.get("user_id"),
            "username": session.get("username"),
            "role": session.get("role")
        }

@app.before_request
def protect_routes():
    public_paths = ["/", "/login"]

    if request.path.startswith("/static"):
        return

    if request.path in public_paths:
        return

    if g.user is None:
        return redirect(url_for("auth.login"))

def init_db():
    con = sqlite3.connect(DB_FILE)
    cur = con.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS customers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        address TEXT,
        next_invoice_no INTEGER DEFAULT 560
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        price REAL NOT NULL
    )
    """)

    con.commit()
    con.close()
# ---------------- HOME PAGE ----------------
from flask import send_from_directory

@app.route("/download/<filename>")
def download_pdf(filename):
    return send_from_directory(
        PDF_DIR,
        filename,
        as_attachment=False  # IMPORTANT for mobile
    )

@app.route("/")
def home():
    return render_template("home.html")





@app.route("/dashboard")
def index():
    # 🔒 ADMIN ONLY
    if g.user is None or g.user.get("role") != "admin":
        flash("Unauthorized access.", "danger")
        return redirect(url_for("inventory"))

    con = sqlite3.connect(DB_FILE)
    cur = con.cursor()

    cur.execute("SELECT id, name, next_invoice_no FROM customers ORDER BY name")
    customers = cur.fetchall()

    cur.execute("SELECT id, name, price FROM products ORDER BY name")
    products = cur.fetchall()

    invoice_no = 560
    if customers:
        cid = customers[0][0]
        cur.execute(
            "SELECT COALESCE(next_invoice_no, 560) FROM customers WHERE id=?",
            (cid,)
        )
        invoice_no = cur.fetchone()[0]

    con.close()

    return render_template(
        "dashboard.html",
        customers=customers,
        products=products,
        invoice_no=invoice_no,
        today=datetime.today().strftime("%d/%m/%Y")
    )


@app.route("/generate", methods=["POST"])
def generate():
    data = request.get_json(silent=True)
    if not data:
        return "Invalid JSON request", 400

    invoice_no = int(data["invoice_no"])
    date = data["date"]
    customer_id = int(data["customer_id"])
    items = data["items"]


    total = sum(item["amount"] for item in items)

    # --- Fetch customer name & address ---
    con = sqlite3.connect(DB_FILE)
    cur = con.cursor()
    cur.execute(
        "SELECT name, address FROM customers WHERE id=?",
        (customer_id,)
    )
    row = cur.fetchone()
    con.close()

    if not row:
        return "Customer not found", 400

    customer = {
        "name": row[0],
        "address": row[1] or ""
    }

    pdf_path = os.path.join(
        PDF_DIR,
        f"Invoice_{invoice_no}.pdf"
    )
    if invoice_no <= 0:
        return "Invalid invoice number", 400

    generate_pdf(
        invoice_no=invoice_no,
        date_str=date,
        customer=customer,
        items=items,
        total=total,
        save_path=pdf_path,
        use_letterhead=data["print_letterhead"],
        print_ntn=data["print_ntn"]
    )
    STEP = 3  # same as desktop app
    con = sqlite3.connect(DB_FILE)
    cur = con.cursor()
    cur.execute(
        "UPDATE customers SET next_invoice_no=? WHERE id=?",
        (invoice_no + STEP, customer_id)
    )
    con.commit()
    con.close()
    filename = os.path.basename(pdf_path)
    return {
    "success": True,
    "pdf_url": f"/download/{filename}"
}
@app.route("/next_invoice/<int:customer_id>")
def next_invoice(customer_id):
    con = sqlite3.connect(DB_FILE)
    cur = con.cursor()
    cur.execute(
        "SELECT COALESCE(next_invoice_no, 560) FROM customers WHERE id=?",
        (customer_id,)
    )
    invoice_no = cur.fetchone()[0]
    con.close()

    return {"invoice_no": invoice_no}

@app.route("/add_customer", methods=["POST"])
def add_customer():
    data = request.get_json()
    con = sqlite3.connect(DB_FILE)
    cur = con.cursor()
    cur.execute(
        "INSERT INTO customers (name, address) VALUES (?,?)",
        (data["name"], data.get("address", ""))
    )
    con.commit()
    con.close()
    return "OK"

@app.route("/inventory")
def inventory():
    # ... (user authentication check)

    con = sqlite3.connect(DB_FILE)
    cur = con.cursor()

  
    cur.execute("SELECT id, name FROM lenses ORDER BY name")
    lenses = cur.fetchall()
    cur.execute("SELECT id, name FROM doctors ORDER BY name")
    doctors = cur.fetchall()
    lens_id = request.args.get("lens_id")
    power = request.args.get("power")

    stock_query = """
        SELECT l.id, l.name, s.power,
               COALESCE( SUM(CASE WHEN s.type = 'IN' THEN s.quantity ELSE -s.quantity END),0) AS qty
        FROM stock_transactions s
        JOIN lenses l ON l.id = s.lens_id
    """
    stock_conditions = []
    stock_params = []

    if lens_id:
        stock_conditions.append("l.id = ?")
        stock_params.append(int(lens_id))

    if power:
        # CHANGED: Using "=" instead of "LIKE" for exact power searching
        stock_conditions.append("s.power = ?")
        stock_params.append(power)

    if stock_conditions:
        stock_query += " WHERE " + " AND ".join(stock_conditions)

    stock_query += " GROUP BY l.id, l.name, s.power HAVING qty > 0 ORDER BY l.name"
    cur.execute(stock_query, stock_params)
    stock = cur.fetchall()
    if power and not stock:
        if lens_id:
            cur.execute("SELECT name FROM lenses WHERE id = ?", (lens_id,))
            row = cur.fetchone()
            lens_name = row[0] if row else "Selected Lens"
        else:
            lens_name = "Selected Lens"
        flash(f"Power {power} is not available for {lens_name}.", "warning")


    # 2️⃣ RECENT TRANSACTIONS FILTER (Added rt_doc_id)
    # 2️⃣ RECENT TRANSACTIONS FILTER
    rt_lens_id = request.args.get("rt_lens_id")
    rt_doc_id = request.args.get("rt_doc_id")
    rt_power = request.args.get("rt_power")
    rt_type = request.args.get("rt_type")
    rt_date = request.args.get("rt_date")
    recent_query = """
    SELECT
        l.name,
        s.power,
        s.quantity,
        s.type,
        s.created_at,
        CASE
            WHEN s.type = 'IN' THEN '—'
            ELSE COALESCE(d.name, 'N/A')
        END AS doctor_name
    FROM stock_transactions s
    JOIN lenses l ON l.id = s.lens_id
    LEFT JOIN doctors d ON d.id = s.doctor_id
    WHERE 1=1
    """


    recent_params = []
    
    if rt_lens_id:
        recent_query += " AND l.id = ?"
        recent_params.append(int(rt_lens_id))
    if rt_doc_id:
        recent_query += " AND s.doctor_id = ?"
        recent_params.append(int(rt_doc_id))


    if rt_power:
        recent_query += " AND s.power LIKE ?"
        recent_params.append(f"%{rt_power}%")
    if rt_type:
        recent_query += " AND s.type = ?"
        recent_params.append(rt_type)
    if rt_date:
        recent_query += " AND DATE(s.created_at) = ?"
        recent_params.append(rt_date)

    recent_query += " ORDER BY s.created_at DESC LIMIT 50" # Added limit for performance
    cur.execute(recent_query, recent_params)
    recent = cur.fetchall()

    # 3️⃣ STAFF DELIVERY ACTIVITY SEARCH (Added emp_doc)
    emp = request.args.get("emp")
    emp_lens = request.args.get("emp_lens")
    emp_doc = request.args.get("emp_doc")
    emp_date = request.args.get("emp_date")

    emp_query = """
        SELECT e.employee, l.name, e.power, e.quantity, e.delivered_at,COALESCE(d.name, 'N/A') as doctor_name,'OUT' as action_type
        FROM employee_deliveries e
        JOIN lenses l ON l.id = e.lens_id
        LEFT JOIN doctors d ON d.id = e.doctor_id
    """
    emp_conditions = []
    emp_params = []

    if emp: emp_conditions.append("e.employee = ?"); emp_params.append(emp)
    if emp_lens: emp_conditions.append("l.id = ?"); emp_params.append(int(emp_lens))
    if emp_doc: emp_conditions.append("e.doctor_id = ?"); emp_params.append(int(emp_doc))
    if emp_date: emp_conditions.append("DATE(e.delivered_at) = ?"); emp_params.append(emp_date)

    if emp_conditions: emp_query += " WHERE " + " AND ".join(emp_conditions)
    emp_query += " ORDER BY e.delivered_at DESC"
    cur.execute(emp_query, emp_params)
    employee_log = cur.fetchall()

    cur.execute("SELECT DISTINCT employee FROM employee_deliveries ORDER BY employee")
    staff_list = [row[0] for row in cur.fetchall()]
    con.close()

    return render_template("inventory.html", lenses=lenses, doctors=doctors, stock=stock, 
                           recent=recent, employee_log=employee_log, staff_list=staff_list,user=g.user)

# New Route to Add Doctor
@app.route("/inventory/add-doctor", methods=["POST"])
def add_doctor():
    name = request.form.get("name", "").strip()
    if name:
        con = sqlite3.connect(DB_FILE)
        cur = con.cursor()
        cur.execute("INSERT OR IGNORE INTO doctors (name) VALUES (?)", (name,))
        con.commit()
        con.close()
    return redirect("/inventory")

# Update Stock In/Out to save doctor_id



@app.route("/inventory/add-lens", methods=["GET", "POST"])
def add_lens():
    # If someone opens this URL directly → send them back
    if request.method == "GET":
        return redirect("/inventory")

    # POST request (form submit)
    name = request.form.get("name", "").strip()

    if not name:
        return redirect("/inventory")

    con = sqlite3.connect(DB_FILE)
    cur = con.cursor()
    cur.execute(
        "INSERT OR IGNORE INTO lenses (name) VALUES (?)",
        (name,)
    )
    con.commit()
    con.close()

    return redirect("/inventory")
    
    

@app.route("/inventory/stock-in", methods=["POST"])
def stock_in_out():
    user = g.get("user")
    if not user or user.get("role") not in ["admin", "team"]:
        return redirect(url_for("index"))

    lens_id = request.form.get("lens_id") 
    doctor_id = request.form.get("doctor_id")
    power = request.form.get("power")
    quantity = request.form.get("quantity")
    txn_type = request.form.get("type")  # IN or OUT


    if txn_type == "OUT" and not doctor_id:
        return redirect("/inventory")

    if not lens_id or not power or not quantity:
        return redirect("/inventory")

    quantity = int(quantity)

    con = sqlite3.connect(DB_FILE)
    cur = con.cursor()

    # 1. Check current availability for Stock Out
    if txn_type == "OUT":
        cur.execute("""
            SELECT COALESCE(SUM(
                CASE WHEN type='IN' THEN quantity ELSE -quantity END
            ), 0)
            FROM stock_transactions
            WHERE lens_id=? AND power=?
        """, (lens_id, power))

        available = cur.fetchone()[0]
        
        # 2. Trigger "Stock Not Available" Alert
        if quantity > available:
            con.close()
            flash(f"Error: Stock not available! You have {available} units, but tried to take {quantity}.", "danger")
            return redirect("/inventory")

    # 3. Process Transaction
    cur.execute("""
        INSERT INTO stock_transactions (lens_id, doctor_id, power, quantity, type)
        VALUES (?, ?, ?, ?, ?)
    """, (lens_id, doctor_id, power, quantity, txn_type))

    # Log delivery for staff tracking
    if txn_type == "OUT":
        cur.execute("""
            INSERT INTO employee_deliveries (employee, lens_id, doctor_id, power, quantity)
            VALUES (?, ?, ?, ?, ?)
        """, (user["username"], lens_id, doctor_id, power, quantity))

    con.commit()
    con.close()
    
    # 4. Success Alert
    flash("Transaction processed successfully!", "success")
    return redirect("/inventory")




@app.route("/add_product", methods=["POST"])
def add_product():
    data = request.get_json(silent=True)
    if not data:
        return "Invalid JSON request", 400

    con = sqlite3.connect(DB_FILE)
    cur = con.cursor()
    cur.execute(
        "INSERT INTO products (name, price) VALUES (?,?)",
        (data["name"], float(data["price"]))
    )
    con.commit()
    con.close()
    return "OK"


# ---------------- START SERVER ----------------
if __name__ == "__main__":
    init_db()
    init_auth_tables()
    init_inventory_tables()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)),debug=True)

